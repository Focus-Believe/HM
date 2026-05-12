// Chat functionality
let ws = null;
let currentChatUser = null;

function connectWebSocket() {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws?token=${token}`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => console.log('WebSocket connected');
    ws.onmessage = (event) => handleMessage(JSON.parse(event.data));
    ws.onclose = () => setTimeout(connectWebSocket, 3000);
}

function handleMessage(data) {
    switch(data.type) {
        case 'message':
            displayMessage(data);
            break;
        case 'typing':
            showTypingIndicator(data.from);
            break;
        case 'user_online':
            updateUserStatus(data.user_id, true);
            break;
        case 'user_offline':
            updateUserStatus(data.user_id, false);
            break;
    }
}

function sendMessage(to, text) {
    if (!text.trim()) return;
    
    ws.send(JSON.stringify({
        type: 'dm',
        to: to,
        msg: text
    }));
}

function displayMessage(message) {
    const container = document.getElementById('messages-container');
    const isSent = message.sender_id === currentUser.id;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
    messageDiv.innerHTML = `
        <div class="message-bubble">${escapeHtml(message.message)}</div>
        <div class="message-time">${formatTime(message.created_at)}</div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}
