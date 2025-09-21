document.addEventListener("DOMContentLoaded", () => {
    // LOGIN HANDLER
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const email = document.getElementById("login-email").value;
            const password = document.getElementById("login-password").value;
            const loginError = document.getElementById("login-error");

            try {
                const res = await fetch("/api/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });

                const data = await res.json();
                if (res.ok) {
                    // ✅ Store token and redirect
                    localStorage.setItem("token", data.token);
                    window.location.href = "dashboard.html";
                } else {
                    loginError.textContent = data.message || "Login failed";
                    loginError.style.display = "block";
                }
            } catch (err) {
                loginError.textContent = "Server error, try again later";
                loginError.style.display = "block";
            }
        });
    }

    // SIGNUP HANDLER
    const signupForm = document.getElementById("signup-form");
    if (signupForm) {
        signupForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const name = document.getElementById("signup-name").value;
            const email = document.getElementById("signup-email").value;
            const password = document.getElementById("signup-password").value;
            const signupError = document.getElementById("signup-error");

            try {
                const res = await fetch("/api/signup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, email, password })
                });

                const data = await res.json();
                if (res.ok) {
                    alert("Signup successful! Please log in.");
                    window.location.href = "login.html";
                } else {
                    signupError.textContent = data.message || "Signup failed";
                    signupError.style.display = "block";
                }
            } catch (err) {
                signupError.textContent = "Server error, try again later";
                signupError.style.display = "block";
            }
        });
    }
});
