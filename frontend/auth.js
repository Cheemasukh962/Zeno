/* Zeno — demo-grade client-side auth (localStorage).
 * NOT production security: accounts live in the browser, passwords are hashed but
 * there is no server verification. Good enough to demo the signup/login + role flow.
 * Upgrade path: move signup/login/session to a backend (SQLite or Redis) later. */
(function () {
  const USERS = "zeno_users", SESSION = "zeno_session";

  async function hash(s) {
    try {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
      return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {
      // fallback for non-secure contexts (e.g. file://) — still not plaintext
      let h = 5381;
      for (let i = 0; i < s.length; i++) h = ((h << 5) + h) ^ s.charCodeAt(i);
      return "f" + (h >>> 0).toString(16);
    }
  }

  const readUsers = () => { try { return JSON.parse(localStorage.getItem(USERS)) || {}; } catch (e) { return {}; } };
  const writeUsers = (u) => localStorage.setItem(USERS, JSON.stringify(u));
  const setSession = (u) => localStorage.setItem(SESSION,
    JSON.stringify({ name: u.name, email: u.email, role: u.role, ts: Date.now() }));

  async function signup({ name, email, password, role }) {
    name = (name || "").trim(); email = (email || "").trim().toLowerCase();
    role = role === "admin" ? "admin" : "user";
    if (!name || !email || !password) throw new Error("Please fill in every field.");
    if (!/^\S+@\S+\.\S+$/.test(email)) throw new Error("That doesn't look like a valid email.");
    if (password.length < 6) throw new Error("Password must be at least 6 characters.");
    const users = readUsers();
    if (users[email]) throw new Error("An account with this email already exists — sign in instead.");
    users[email] = { name, email, role, pass: await hash(password), created: Date.now() };
    writeUsers(users); setSession(users[email]);
    return users[email];
  }

  async function login({ email, password, role }) {
    email = (email || "").trim().toLowerCase();
    const u = readUsers()[email];
    if (!u) throw new Error("No account found for that email — create one first.");
    if (u.pass !== await hash(password)) throw new Error("Incorrect password.");
    if (role && u.role !== role)
      throw new Error(`That's a ${u.role} account — flip the toggle to ${u.role}.`);
    setSession(u); return u;
  }

  function session() { try { return JSON.parse(localStorage.getItem(SESSION)); } catch (e) { return null; } }
  function logout() { localStorage.removeItem(SESSION); location.href = "login.html"; }
  function routeFor(role) { return role === "admin" ? "admin.html" : "index.html"; }

  // Page guard. role: "admin" | "user" | "any". Redirects if not allowed; returns the session.
  function requireRole(role) {
    const s = session();
    if (!s) { location.href = "login.html"; return null; }
    if (role && role !== "any" && s.role !== role) { location.href = routeFor(s.role); return null; }
    return s;
  }

  function initials(name) {
    return (name || "?").trim().split(/\s+/).slice(0, 2).map(w => w[0].toUpperCase()).join("");
  }

  window.Zeno = { hash, signup, login, session, logout, routeFor, requireRole, initials };
})();
