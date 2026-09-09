import React, { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  Check,
  ChevronDown,
  CloudSun,
  Compass,
  Download,
  FileUp,
  Heart,
  History,
  Info,
  Loader2,
  LogOut,
  Map,
  MapPin,
  Menu,
  Moon,
  Plane,
  Plus,
  Share2,
  Sparkles,
  Sun,
  TrendingUp,
  UserRound,
  Utensils,
  Wallet,
} from "lucide-react";
import { fetchTripById, fetchTrips, generateTrip, uploadDocument } from "./api";
import { firebaseEnabled, loginWithEmail, loginWithGoogle, logout, registerWithEmail, subscribeToAuth } from "./firebase";
import { interestOptions, styleOptions } from "./data";
import PopularPlaces from "./PopularPlaces";
import FavoriteDestinations from "./FavoriteDestinations";

const today = new Date().toISOString().slice(0, 10);
const initialForm = {
  destination: "",
  start_date: today,
  end_date: today,
  budget: 5000,
  currency: "INR",
  travelers: 2,
  interests: ["Food", "Culture", "Photography"],
  travel_style: "balanced",
  notes: "",
  selected_attractions: [],
};

const formatCurrency = (value, currency = "INR") => {
  const curr = (currency || "INR").toUpperCase();
  const locale = curr === "INR" ? "en-IN" : "en-US";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: curr,
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
};

function App() {
  const [user, setUser] = useState(null);
  const [dark, setDark] = useState(false);
  useEffect(() => subscribeToAuth(setUser), []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  return (
    <BrowserRouter>
      <Shell user={user} setUser={setUser} dark={dark} setDark={setDark} />
    </BrowserRouter>
  );
}

function Shell({ user, setUser, dark, setDark }) {
  const navigate = useNavigate();
  const location = useLocation();
  async function signOut() {
    await logout();
    setUser(null);
    navigate("/");
  }
  const plain = ["/login", "/register"].includes(location.pathname);
  return (
    <>
      <Nav user={user} onLogout={signOut} dark={dark} setDark={setDark} plain={plain} />
      <Routes>
        <Route path="/" element={<Home user={user} />} />
        <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login onLogin={setUser} />} />
        <Route path="/register" element={user ? <Navigate to="/dashboard" replace /> : <Register onLogin={setUser} />} />
        <Route element={<Protected user={user} />}>
          <Route path="/dashboard" element={<Dashboard user={user} />} />
          <Route path="/create-trip" element={<CreateTrip user={user} />} />
          <Route path="/trip/:id" element={<TripDetails user={user} />} />
          <Route path="/history" element={<HistoryPage user={user} />} />
          <Route path="/profile" element={<Profile user={user} onLogout={signOut} />} />
          <Route path="/settings" element={<Profile user={user} onLogout={signOut} settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

function Protected({ user }) {
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

function Nav({ user, onLogout, dark, setDark, plain }) {
  const [open, setOpen] = useState(false);
  return (
    <header className={`nav ${plain ? "nav-plain" : ""}`}>
      <NavLink className="logo" to="/">
        <span><Plane size={19} /></span>TravelFlow AI
      </NavLink>
      <button className="mobile-menu" onClick={() => setOpen(!open)}><Menu /></button>
      <nav className={open ? "open" : ""}>
        {!user ? (
          <>
            <a href="/#features">Features</a>
            <a href="/#about">About</a>
            <a href="/#contact">Contact</a>
          </>
        ) : (
          <>
            <NavLink to="/dashboard">Dashboard</NavLink>
            <NavLink to="/create-trip">Plan Trip</NavLink>
            <NavLink to="/history">My Trips</NavLink>
          </>
        )}
        <button className="theme" onClick={() => setDark(!dark)} aria-label="Toggle dark mode">
          {dark ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        {user ? (
          <>
            <NavLink className="profile-link" to="/profile">
              <UserRound size={17} />
              {user.displayName?.split(" ")[0] || "Profile"}
            </NavLink>
            <button className="logout-link" onClick={onLogout}>Logout</button>
          </>
        ) : (
          <>
            <NavLink className="login-link" to="/login">Login</NavLink>
            <NavLink className="button small" to="/register">Get started</NavLink>
          </>
        )}
      </nav>
    </header>
  );
}

function Home({ user }) {
  return (
    <main>
      <section className="hero">
        <div className="hero-content">
          <p className="eyebrow">YOUR JOURNEY, INTELLIGENTLY PLANNED</p>
          <h1>Travel anywhere. <em>Any budget.</em></h1>
          <p className="hero-copy">
            Tell our AI travel assistant where you want to go and what you want to spend. We build personalized, balanced itineraries tailored to your unique travel style.
          </p>
          <div className="hero-actions">
            <NavLink className="button" to={user ? "/create-trip" : "/register"}>
              Plan your trip <ArrowRight size={18} />
            </NavLink>
            <a className="text-link" href="#how">See how it works</a>
          </div>
          <div className="hero-proof">
            <div className="avatars"><i>J</i><i>M</i><i>A</i><i>S</i></div>
            <span>Loved by 12,000+ curious travelers worldwide</span>
          </div>
        </div>
        <div className="hero-card">
          <div className="trip-chip"><span>✦</span> AI Smart Planning</div>
          <div className="hero-destination">
            <p>ANY DESTINATION</p>
            <h2>Personalized Travel</h2>
            <span>Dynamic dates · Budget-optimized · Custom interests</span>
          </div>
          <div className="mini-plan">
            <div><CalendarDays size={18} /><span><b>Every Day</b> · Intelligent schedule & food tips</span></div>
            <div className="mini-dots"><b></b><b></b><b></b></div>
          </div>
        </div>
      </section>
      <section id="features" className="section">
        <p className="eyebrow">SMARTER TRAVEL STARTS HERE</p>
        <h2>Everything you need,<br /><em>nothing you don’t.</em></h2>
        <div className="feature-grid">
          <Feature icon={<Sparkles />} title="AI-powered itineraries" text="Thoughtful, personalized days built around the way you love to travel." />
          <Feature icon={<Wallet />} title="Budgets that work" text="Intelligent budget analysis and cost-saving suggestions for any budget level." />
          <Feature icon={<Map />} title="All in one place" text="Maps, plans, local food highlights, and travel tips — beautifully organized." />
        </div>
      </section>
      <footer id="contact">
        <div className="logo"><span><Plane size={18} /></span>TravelFlow AI</div>
        <p>Plan anywhere. Experience more.</p>
        <span>© 2026 TravelFlow. Made for every traveler.</span>
      </footer>
    </main>
  );
}

function Feature({ icon, title, text }) {
  return (
    <article className="feature">
      <span className="feature-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}

function AuthLayout({ title, subtitle, children }) {
  return (
    <main className="auth-page">
      <div className="auth-art">
        <p>TRAVELFLOW</p>
        <h1>Every journey begins<br />with a little <em>wonder.</em></h1>
        <span>✦</span>
      </div>
      <section className="auth-card">
        <p className="eyebrow">WELCOME TO TRAVELFLOW</p>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        {children}
      </section>
    </main>
  );
}

function Login({ onLogin }) {
  const navigate = useNavigate();
  const [data, setData] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await loginWithEmail(data.email, data.password));
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const google = async () => {
    try {
      onLogin(await loginWithGoogle());
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <AuthLayout title="Welcome back." subtitle="Your next adventure is waiting.">
      <form className="auth-form" onSubmit={submit}>
        <label>Email address<input required type="email" placeholder="you@example.com" onChange={(e) => setData({ ...data, email: e.target.value })} /></label>
        <label>Password<input required type="password" placeholder="••••••••" onChange={(e) => setData({ ...data, password: e.target.value })} /></label>
        <div className="form-row">
          <label className="check"><input type="checkbox" />Remember me</label>
        </div>
        {error && <p className="error">{error}</p>}
        <button className="button" disabled={busy}>{busy && <Loader2 className="spin" />}Log in <ArrowRight size={17} /></button>
      </form>
      <div className="or">or continue with</div>
      <button className="google" onClick={google}>G <span>Google</span></button>
      <p className="auth-switch">New here? <NavLink to="/register">Create an account</NavLink></p>
      {!firebaseEnabled && <p className="demo-note">Demo mode: register an account to sign in.</p>}
    </AuthLayout>
  );
}

function Register({ onLogin }) {
  const navigate = useNavigate();
  const [data, setData] = useState({ name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (data.password.length < 8) return setError("Use at least 8 characters for your password.");
    if (data.password !== data.confirm) return setError("Passwords do not match.");
    try {
      onLogin(await registerWithEmail(data.name, data.email, data.password));
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <AuthLayout title="Begin your story." subtitle="Create your account and start exploring.">
      <form className="auth-form" onSubmit={submit}>
        <label>Full name<input required placeholder="Alex Morgan" onChange={(e) => setData({ ...data, name: e.target.value })} /></label>
        <label>Email address<input required type="email" placeholder="you@example.com" onChange={(e) => setData({ ...data, email: e.target.value })} /></label>
        <label>Password<input required minLength="8" type="password" placeholder="8+ characters" onChange={(e) => setData({ ...data, password: e.target.value })} /></label>
        <label>Confirm password<input required type="password" placeholder="Repeat your password" onChange={(e) => setData({ ...data, confirm: e.target.value })} /></label>
        {error && <p className="error">{error}</p>}
        <button className="button">Create account <ArrowRight size={17} /></button>
      </form>
      <p className="auth-switch">Already a member? <NavLink to="/login">Log in</NavLink></p>
    </AuthLayout>
  );
}

function Dashboard({ user }) {
  const [trips, setTrips] = useState([]);
  useEffect(() => {
    fetchTrips(user.uid).then(setTrips).catch(() => setTrips([]));
  }, [user.uid]);
  const total = trips.length;
  return (
    <main className="app-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR TRAVEL SPACE</p>
          <h1>Welcome back, {user.displayName?.split(" ")[0] || "Traveler"}.</h1>
          <p>Ready to turn your next travel dream into a real plan?</p>
        </div>
        <NavLink className="button" to="/create-trip"><Plus size={18} /> Plan new trip</NavLink>
      </div>
      <div className="stats-cards">
        <Stat icon={<Plane />} label="Total trips" value={total} />
        <Stat icon={<CalendarDays />} label="Upcoming journeys" value={total} />
        <Stat icon={<Sparkles />} label="AI Itineraries" value={total} />
        <Stat icon={<Wallet />} label="Total planned budget" value={formatCurrency(trips.reduce((a, t) => a + (t.plan?.budget || 0), 0) || 5000)} />
      </div>
      <section className="dashboard-grid">
        <article className="dashboard-card">
          <div className="card-title">
            <h2>Recent trips</h2>
            <NavLink to="/history">View all</NavLink>
          </div>
          {trips.length ? trips.slice(0, 3).map((t) => <TripRow key={t.id} trip={t} />) : <EmptyTrips />}
        </article>
        <aside className="dashboard-card actions">
          <h2>Quick actions</h2>
          <NavLink to="/create-trip"><Sparkles />Generate an itinerary <ArrowRight size={16} /></NavLink>
          <NavLink to="/history"><History />Trip history <ArrowRight size={16} /></NavLink>
          <NavLink to="/profile"><UserRound />Profile & settings <ArrowRight size={16} /></NavLink>
        </aside>
      </section>
    </main>
  );
}

function Stat({ icon, label, value }) {
  return (
    <article className="stat-card">
      <span>{icon}</span>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

function EmptyTrips() {
  return (
    <div className="empty-trips">
      <Plane />
      <h3>Your adventure starts here.</h3>
      <p>Tell the AI Assistant where you'd like to go and let it design the perfect trip.</p>
      <NavLink className="text-link" to="/create-trip">Plan a trip <ArrowRight size={16} /></NavLink>
    </div>
  );
}

function TripRow({ trip }) {
  return (
    <NavLink className="trip-row" to={`/trip/${trip.id}`}>
      <span className="trip-thumb"><Plane /></span>
      <div>
        <b>{trip.plan.destination}</b>
        <p>{trip.plan.summary}</p>
      </div>
      <ArrowRight size={17} />
    </NavLink>
  );
}

function CreateTrip({ user }) {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const days = useMemo(() => {
    if (!form.start_date || !form.end_date) return 1;
    const start = new Date(form.start_date);
    const end = new Date(form.end_date);
    const diffTime = end - start;
    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
    return Math.max(1, diffDays + 1);
  }, [form.start_date, form.end_date]);

  const update = (key, value) => setForm((f) => ({ ...f, [key]: ["budget", "travelers"].includes(key) ? Number(value) : value }));
  const toggle = (i) => setForm((f) => ({ ...f, interests: f.interests.includes(i) ? f.interests.filter((x) => x !== i) : [...f.interests, i] }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.destination.trim()) {
      return setError("Please enter a destination to explore.");
    }
    if (form.end_date < form.start_date) {
      return setError("Return date must be on or after departure date.");
    }
    if (form.budget <= 0) {
      return setError("Please enter a valid budget amount.");
    }
    if (form.travelers < 1) {
      return setError("Number of travelers must be at least 1.");
    }

    setLoading(true);
    setError("");
    try {
      const plan = await generateTrip({ ...form, user_id: user.uid });
      const cached = JSON.parse(localStorage.getItem("latest-plan") || "{}");
      localStorage.setItem("latest-plan", JSON.stringify(plan));
      navigate(`/trip/${plan.id || cached.id || "latest"}`, { state: { plan } });
    } catch (err) {
      setError(err.message || "Failed to generate itinerary. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-page">
      <div className="page-heading compact-page">
        <div>
          <p className="eyebrow">AI TRAVEL ASSISTANT</p>
          <h1>Plan your custom escape.</h1>
          <p>Tell the AI your destination, dates, budget, and travel preferences.</p>
        </div>
      </div>
      <form className="trip-builder" onSubmit={submit}>
        <section className="form-card">
          <label>
            Where would you like to go?
            <input
              placeholder="e.g. Goa, Paris, Tokyo, Dubai, Manali, New York..."
              value={form.destination}
              onChange={(e) => update("destination", e.target.value)}
              required
            />
          </label>
          <div className="form-grid">
            <label>Departure<input type="date" value={form.start_date} onChange={(e) => update("start_date", e.target.value)} required /></label>
            <label>Return<input type="date" value={form.end_date} onChange={(e) => update("end_date", e.target.value)} required /></label>
          </div>
          <div className="form-grid">
            <label>
              Total Budget
              <div style={{ display: "flex", gap: "8px" }}>
                <select
                  value={form.currency}
                  onChange={(e) => update("currency", e.target.value)}
                  style={{ width: "90px", padding: "10px", borderRadius: "8px", border: "1px solid var(--border)" }}
                >
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                </select>
                <input
                  min="1"
                  type="number"
                  value={form.budget}
                  onChange={(e) => update("budget", e.target.value)}
                  style={{ flex: 1 }}
                  required
                />
              </div>
            </label>
            <label>
              Travelers
              <input min="1" max="20" type="number" value={form.travelers} onChange={(e) => update("travelers", e.target.value)} required />
            </label>
          </div>
          <label>Travel style</label>
          <div className="choice-row">
            {styleOptions.map((s) => (
              <button type="button" key={s.value} className={form.travel_style === s.value ? "selected" : ""} onClick={() => update("travel_style", s.value)}>
                {s.label}
              </button>
            ))}
          </div>
          <label>What are you interested in?</label>
          <div className="choice-row">
            {interestOptions.map((i) => (
              <button type="button" key={i} className={form.interests.includes(i) ? "selected" : ""} onClick={() => toggle(i)}>
                {form.interests.includes(i) && <Check size={14} />} {i}
              </button>
            ))}
          </div>
          <PopularPlaces destination={form.destination} selected={form.selected_attractions} onChange={(v) => update("selected_attractions", v)} />
          {error && <p className="error">{error}</p>}
          <button className="button generate" disabled={loading}>
            {loading ? <Loader2 className="spin" /> : <Sparkles />}
            {loading ? "AI Assistant is crafting your itinerary..." : `Generate ${days}-Day AI Itinerary`}
            <ArrowRight size={17} />
          </button>
        </section>
        <aside className="builder-aside">
          <span>✦</span>
          <h2>AI Travel Consultant</h2>
          <p>The AI dynamically analyzes your destination, duration, budget, and travel style to generate the best possible trip.</p>
          <div>
            <b>{days} {days === 1 ? "day" : "days"}</b>
            <b>{form.travelers} {form.travelers === 1 ? "traveler" : "travelers"}</b>
            <b>{form.travel_style.toUpperCase()}</b>
          </div>
        </aside>
      </form>
    </main>
  );
}

function TripDetails({ user }) {
  const { id } = useParams();
  const location = useLocation();
  const [plan, setPlan] = useState(location.state?.plan || null);
  const [upload, setUpload] = useState("");

  useEffect(() => {
    if (plan) return;
    fetchTrips(user?.uid)
      .then(async (items) => {
        const found = items.find((x) => String(x.id) === id)?.plan;
        if (found) {
          setPlan(found);
        } else {
          const direct = await fetchTripById(id);
          if (direct) {
            setPlan(direct);
          } else {
            setPlan(JSON.parse(localStorage.getItem("latest-plan") || "null"));
          }
        }
      })
      .catch(async () => {
        const direct = await fetchTripById(id).catch(() => null);
        setPlan(direct || JSON.parse(localStorage.getItem("latest-plan") || "null"));
      });
  }, [id, user?.uid, plan]);

  if (!plan) return <main className="app-page"><EmptyTrips /></main>;

  const map = `https://maps.google.com/maps?q=${encodeURIComponent(plan.map_query || plan.destination)}&output=embed`;
  const budgetAnalysis = plan.budget_analysis;

  return (
    <main className="app-page">
      <div className="trip-summary">
        <div>
          <p className="eyebrow">YOUR AI-CRAFTED ITINERARY</p>
          <h1>{plan.destination}</h1>
          <p>{plan.summary}</p>
        </div>
        <div className="trip-actions">
          <button onClick={() => window.print()}><Download size={17} /> Download PDF</button>
          <button onClick={() => navigator.clipboard?.writeText(window.location.href)}><Share2 size={17} /> Share</button>
        </div>
      </div>

      <div className="trip-meta">
        <span><CalendarDays /> {plan.start_date ? `${plan.start_date} → ${plan.end_date || ""}` : `${plan.duration_days || plan.itinerary?.length || 1} Days`}</span>
        <span><UserRound size={16} /> {plan.travelers || 1} {plan.travelers === 1 ? "Traveler" : "Travelers"} · {(plan.travel_style || "Balanced").toUpperCase()}</span>
        <span><CloudSun /> {plan.weather?.temperature_c != null ? `${plan.weather.temperature_c}°C · ${plan.weather.description || ""}` : (plan.weather?.description || "Weather ready")}</span>
        <span><Wallet /> {formatCurrency(plan.budget, plan.currency)}</span>
      </div>

      {budgetAnalysis && (
        <section className="budget-assistant-panel" style={{ margin: "20px 0", padding: "18px 24px", borderRadius: "14px", background: "var(--card-bg, #ffffff)", border: "1px solid var(--border, #e2e8f0)", boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <TrendingUp size={20} color="#6366f1" />
              <h3 style={{ margin: 0, fontSize: "1.1rem" }}>AI Budget & Optimization Analysis</h3>
            </div>
            <span style={{ fontSize: "0.85rem", fontWeight: 600, padding: "4px 10px", borderRadius: "20px", background: budgetAnalysis.budget_status === "exceeds_budget" ? "#fef3c7" : "#ecfdf5", color: budgetAnalysis.budget_status === "exceeds_budget" ? "#92400e" : "#065f46" }}>
              {budgetAnalysis.budget_status === "exceeds_budget" ? "Budget Optimized with Trade-offs" : "Within Requested Budget"}
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", marginBottom: "14px" }}>
            <div style={{ padding: "10px", background: "rgba(99, 102, 241, 0.05)", borderRadius: "8px" }}>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted, #64748b)" }}>Requested Budget</p>
              <strong style={{ fontSize: "1.1rem" }}>{formatCurrency(budgetAnalysis.requested_budget || plan.budget, plan.currency)}</strong>
            </div>
            <div style={{ padding: "10px", background: "rgba(99, 102, 241, 0.05)", borderRadius: "8px" }}>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted, #64748b)" }}>Estimated Real Cost</p>
              <strong style={{ fontSize: "1.1rem" }}>{formatCurrency(budgetAnalysis.estimated_cost, plan.currency)}</strong>
            </div>
            <div style={{ padding: "10px", background: "rgba(99, 102, 241, 0.05)", borderRadius: "8px" }}>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted, #64748b)" }}>Cost Difference</p>
              <strong style={{ fontSize: "1.1rem", color: budgetAnalysis.difference > 0 ? "#dc2626" : "#16a34a" }}>
                {budgetAnalysis.difference > 0 ? `+${formatCurrency(budgetAnalysis.difference, plan.currency)}` : formatCurrency(budgetAnalysis.difference, plan.currency)}
              </strong>
            </div>
          </div>
          {budgetAnalysis.advice && (
            <p style={{ fontSize: "0.92rem", lineHeight: 1.5, color: "var(--text-primary, #334155)", margin: "0 0 10px 0" }}>
              <strong>AI Advice:</strong> {budgetAnalysis.advice}
            </p>
          )}
          {budgetAnalysis.cost_saving_tips?.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {budgetAnalysis.cost_saving_tips.map((tip, idx) => (
                <span key={idx} style={{ fontSize: "0.82rem", background: "var(--tag-bg, #f1f5f9)", padding: "4px 8px", borderRadius: "6px", color: "var(--text-secondary, #475569)" }}>
                  💡 {tip}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="itinerary-layout">
        <section>
          <div className="map-box"><iframe title="Trip location" src={map} /></div>
          <h2>Day-by-day plan</h2>
          {plan.itinerary?.map((day) => (
            <article className="day-plan" key={day.day}>
              <div className="day-number">
                DAY {day.day}
                <span>{day.date}</span>
              </div>
              <div>
                {day.activities.map((a, actIdx) => (
                  <div className="activity" key={actIdx}>
                    <time>{a.time}</time>
                    <div>
                      <h3>{a.place}</h3>
                      <p>{a.description}</p>
                      <span>{a.duration} {a.estimated_cost ? `· ${formatCurrency(a.estimated_cost, plan.currency)}` : ""}</span>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </section>

        <aside className="details-side">
          <section>
            <h3>Budget overview</h3>
            {Object.entries(plan.budget_breakdown || {}).map(([k, v]) => (
              <p key={k}>
                <span style={{ textTransform: "capitalize" }}>{k}</span>
                <b>{formatCurrency(v, plan.currency)}</b>
              </p>
            ))}
          </section>

          {plan.food_recommendations?.length > 0 && (
            <section>
              <h3><Utensils size={16} style={{ marginRight: 6 }} />Local Food & Delicacies</h3>
              {plan.food_recommendations.map((food, idx) => (
                <p className="packing" key={idx}>🍽️ {food}</p>
              ))}
            </section>
          )}

          {plan.transport_suggestions?.length > 0 && (
            <section>
              <h3><Compass size={16} style={{ marginRight: 6 }} />Transit Suggestions</h3>
              {plan.transport_suggestions.map((transit, idx) => (
                <p className="packing" key={idx}>🚇 {transit}</p>
              ))}
            </section>
          )}

          {plan.accommodation_suggestions?.length > 0 && (
            <section>
              <h3><MapPin size={16} style={{ marginRight: 6 }} />Stay Suggestions</h3>
              {plan.accommodation_suggestions.map((stay, idx) => (
                <p className="packing" key={idx}>🏨 {stay}</p>
              ))}
            </section>
          )}

          <section>
            <h3>Packing list</h3>
            {plan.packing_tips?.map((x, idx) => (
              <p className="packing" key={idx}><Check size={15} />{x}</p>
            ))}
          </section>

          <section>
            <h3>Travel documents</h3>
            <label className="upload">
              <input
                type="file"
                onChange={async (e) => {
                  if (e.target.files?.[0]) setUpload((await uploadDocument(e.target.files[0])).url);
                }}
              />
              <FileUp /> Upload booking or ID
            </label>
            {upload && <a href={upload} target="_blank" rel="noopener noreferrer">Document uploaded</a>}
          </section>

          <section>
            <h3>Local tips</h3>
            {plan.local_tips?.map((x, idx) => (
              <p className="packing" key={idx}>✦ {x}</p>
            ))}
          </section>
        </aside>
      </div>
    </main>
  );
}

function HistoryPage({ user }) {
  const [trips, setTrips] = useState([]);
  useEffect(() => {
    fetchTrips(user.uid).then(setTrips).catch(() => setTrips([]));
  }, [user.uid]);
  return (
    <main className="app-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR MEMORIES</p>
          <h1>Trip history.</h1>
          <p>All the journeys and AI itineraries you’ve planned, in one place.</p>
        </div>
        <NavLink className="button" to="/create-trip"><Plus size={18} /> Plan a trip</NavLink>
      </div>
      <section className="history-page">
        {trips.length ? trips.map((t) => <TripRow key={t.id} trip={t} />) : <EmptyTrips />}
      </section>
    </main>
  );
}

function Profile({ user, onLogout, settings }) {
  return (
    <main className="app-page profile-page">
      <p className="eyebrow">{settings ? "PREFERENCES" : "YOUR PROFILE"}</p>
      <h1>{settings ? "Settings" : "Traveler profile."}</h1>
      <section className="profile-card">
        <div className="profile-avatar">{user.displayName?.[0] || "T"}</div>
        <div>
          <h2>{user.displayName || "Traveler"}</h2>
          <p>{user.email}</p>
        </div>
      </section>
      <section className="settings-list">
        <FavoriteDestinations firebaseUid={user.uid} />
      </section>
      <button className="danger" onClick={onLogout}><LogOut size={17} /> Log out</button>
    </main>
  );
}

export default App;
