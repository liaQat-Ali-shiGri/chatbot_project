// Global variables
let currentUser = null;
let currentMessageId = null;

// Login handler
document.getElementById("google-login").onclick = async () => {
    const email = prompt("Enter your email (for testing):", "student@vu.edu.pk");
    const name = prompt("Enter your name:", "Student");
    
    if (email && name) {
        try {
            const response = await fetch("http://localhost:5000/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: email, name: name })
            });
            const data = await response.json();
            
            if (data.success) {
                currentUser = data.user;
                localStorage.setItem("user_email", email);
                localStorage.setItem("user_name", name);
                
                document.getElementById("login-section").style.display = "none";
                document.getElementById("chat-section").style.display = "block";
                
                addMessage("bot", `Welcome ${name}! I'm your LLaMA 3 chatbot. Ask me anything.`);
            }
        } catch (error) {
            alert("Error connecting to server. Make sure backend is running on port 5000");
        }
    }
};

// Logout handler
document.getElementById("logout-btn").onclick = async () => {
    await fetch("http://localhost:5000/api/logout", { method: "POST" });
    localStorage.clear();
    currentUser = null;
    document.getElementById("login-section").style.display = "block";
    document.getElementById("chat-section").style.display = "none";
    document.getElementById("chat-box").innerHTML = '<div class="message bot"><strong>Bot:</strong> Hello! I\'m your LLaMA 3 chatbot. Ask me anything!</div>';
};

// Check if already logged in
if (localStorage.getItem("user_email")) {
    document.getElementById("google-login").click();
}

// Send message
document.getElementById("send-btn").onclick = sendMessage;
document.getElementById("user-input").addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;
    
    // Add user message to chat
    addMessage("you", message);
    input.value = "";
    
    // Show typing indicator
    const typingId = addMessage("bot", "🤔 Thinking...", true);
    
    try {
        const response = await fetch("http://localhost:5000/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        removeMessage(typingId);
        
        // Add bot response
        currentMessageId = data.message_id;
        addMessage("bot", data.response);
        
    } catch (error) {
        removeMessage(typingId);
        addMessage("bot", "❌ Error: Could not connect to server. Make sure backend is running.");
    }
}

function addMessage(sender, text, isTyping = false) {
    const chatBox = document.getElementById("chat-box");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${sender === 'you' ? 'you' : 'bot'}`;
    if (isTyping) msgDiv.id = "typing-indicator";
    msgDiv.innerHTML = `<strong>${sender === 'you' ? 'You' : 'Bot'}:</strong> ${text}`;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return msgDiv;
}

function removeMessage(element) {
    if (element && element.remove) element.remove();
}

// Rating buttons
document.querySelectorAll(".rating-btn").forEach(btn => {
    btn.onclick = () => {
        document.querySelectorAll(".rating-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
    };
});

// Submit feedback
document.getElementById("submit-feedback").onclick = async () => {
    const activeRating = document.querySelector(".rating-btn.active");
    if (!activeRating) {
        alert("Please rate the response first!");
        return;
    }
    
    const rating = activeRating.getAttribute("data-rating");
    const correctness = document.getElementById("correctness").value;
    const lengthType = document.getElementById("length-type").value;
    
    try {
        const response = await fetch("http://localhost:5000/api/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message_id: currentMessageId,
                rating: rating,
                correctness: correctness,
                length_type: lengthType
            })
        });
        
        if (response.ok) {
            alert("✅ Thank you for your feedback!");
            // Reset rating buttons
            document.querySelectorAll(".rating-btn").forEach(b => b.classList.remove("active"));
        }
    } catch (error) {
        alert("Error saving feedback");
    }
};