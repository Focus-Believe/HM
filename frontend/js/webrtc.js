// WebRTC for voice/video calls
let localStream = null;
let peerConnection = null;
const configuration = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

async function startCall(callType, targetUser) {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: callType === 'video'
        });
        
        peerConnection = new RTCPeerConnection(configuration);
        
        localStream.getTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });
        
        peerConnection.ontrack = (event) => {
            const remoteVideo = document.getElementById('remote-video');
            if (remoteVideo) remoteVideo.srcObject = event.streams[0];
        };
        
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        
        // Send offer to target user via WebSocket
        ws.send(JSON.stringify({
            type: 'webrtc_offer',
            target: targetUser,
            sdp: offer
        }));
        
    } catch (error) {
        console.error('Call failed:', error);
        showToast('Cannot start call. Check permissions.', 'error');
    }
}

function endCall() {
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }
    if (peerConnection) {
        peerConnection.close();
    }
    localStream = null;
    peerConnection = null;
}
