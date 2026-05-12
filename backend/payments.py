import stripe
from backend.config import settings

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY

class PaymentManager:
    async def create_payment_intent(self, amount: int, currency: str = "usd") -> dict:
        """Create Stripe payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata={"integration_check": "accept_a_payment"}
            )
            return {
                "client_secret": intent.client_secret,
                "amount": intent.amount,
                "currency": intent.currency
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def create_subscription(self, customer_id: str, price_id: str) -> dict:
        """Create subscription for premium features"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def handle_webhook(self, payload: bytes, sig_header: str, endpoint_secret: str) -> dict:
        """Handle Stripe webhook"""
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            return {"type": event["type"], "data": event["data"]["object"]}
        except Exception as e:
            return {"error": str(e)}

payment_manager = PaymentManager()
