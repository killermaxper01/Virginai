function askAI() {
    const q = document.getElementById("question").value;
    const ans = document.getElementById("answer");

    if (!q.trim()) {
        ans.innerHTML = "Please enter a question.";
        return;
    }

    ans.innerHTML = "Thinking...";

    fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q })
    })
    .then(res => res.json())
    .then(data => {
        ans.innerHTML = data.answer;
    })
    .catch(() => {
        ans.innerHTML = "Server error. Try again later.";
    });
}
