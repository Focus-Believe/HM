import openai
from transformers import pipeline
from textblob import TextBlob
from typing import Dict, List
from backend.config import settings
import json

class AIAssistant:
    def __init__(self):
        self.conversations: Dict[int, List[Dict]] = {}
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
        self.sentiment_analyzer = None
        if settings.ENABLE_SENTIMENT_ANALYSIS:
            try:
                self.sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
            except:
                pass
    
    async def get_response(self, user_id: int, message: str) -> str:
        """Get AI response based on message"""
        
        # Analyze sentiment
        sentiment = await self.analyze_sentiment(message)
        
        # Store conversation history
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append({"role": "user", "content": message})
        
        # Keep only last 10 messages
        if len(self.conversations[user_id]) > 10:
            self.conversations[user_id] = self.conversations[user_id][-10:]
        
        # Get response from OpenAI or fallback
        if settings.OPENAI_API_KEY:
            response = await self.get_openai_response(message)
        else:
            response = self.get_fallback_response(message, sentiment)
        
        self.conversations[user_id].append({"role": "assistant", "content": response})
        return response
    
    async def get_openai_response(self, message: str) -> str:
        """Get response from OpenAI API"""
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful chat assistant for a messaging app."},
                    {"role": "user", "content": message}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI error: {e}")
            return "I'm having trouble responding right now. Please try again later."
    
    async def analyze_sentiment(self, message: str) -> str:
        """Analyze sentiment of message"""
        if self.sentiment_analyzer:
            try:
                result = self.sentiment_analyzer(message)[0]
                return result['label']
            except:
                pass
        
        # Fallback using TextBlob
        blob = TextBlob(message)
        polarity = blob.sentiment.polarity
        if polarity > 0.5:
            return "POSITIVE"
        elif polarity < -0.5:
            return "NEGATIVE"
        return "NEUTRAL"
    
    def get_fallback_response(self, message: str, sentiment: str) -> str:
        """Fallback response when OpenAI is not available"""
        responses = {
            "POSITIVE": ["That's great to hear! 😊", "Awesome! 👍", "I'm glad to hear that!"],
            "NEGATIVE": ["I'm sorry you feel that way. 😔", "That sounds tough. Want to talk about it?", "I hope things get better soon."],
            "NEUTRAL": ["Interesting! Tell me more.", "I see. How can I help you with that?", "Thanks for sharing!"]
        }
        
        import random
        return random.choice(responses.get(sentiment, responses["NEUTRAL"]))
    
    async def detect_hate_speech(self, message: str) -> bool:
        """Detect hate speech in message"""
        hate_keywords = ['hate', 'kill', 'stupid', 'ugly', 'worthless']
        return any(keyword in message.lower() for keyword in hate_keywords)
