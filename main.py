from fasthtml.common import *
from fastsql import Database
import os
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# --- Configuration ---
def get_db_url():
    # 1. Production / Container (Standard Env Var)
    url = os.getenv("DATABASE_URL")
    if url: return url.replace("postgres://", "postgresql://")
    
    # 2. Local Host Development (Custom Env Var to avoid container conflict)
    host_url = os.getenv("HOST_DATABASE_URL")
    if host_url: return host_url.replace("postgres://", "postgresql://")

    # 3. Specific Provider Fallbacks
    non_pooling_url = os.getenv("POSTGRES_URL_NON_POOLING")
    if non_pooling_url: return non_pooling_url.replace("postgres://", "postgresql://")
    pg_url = os.getenv("POSTGRES_URL")
    if pg_url: return pg_url.replace("postgres://", "postgresql://")
    
    # 4. Final Fallback (Default Local Docker)
    return "postgresql://postgres:postgres@localhost:5432/postgres"

db_url = get_db_url()
db = Database(db_url)

FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    print("WARNING: FERNET_KEY not found in env, generating temporary one.")
    FERNET_KEY = Fernet.generate_key().decode()

cipher_suite = Fernet(FERNET_KEY)

# --- Encryption Helpers ---
def encrypt_value(value: str) -> str:
    if not value: return ""
    return cipher_suite.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    if not encrypted_value: return ""
    try:
        return cipher_suite.decrypt(encrypted_value.encode()).decode()
    except:
        return ""

# --- Enums ---
class LeisureCentre(str, Enum):
    HENDON = "hendon-leisure-centre"
    COPTHALL = "barnet-copthall-leisure-centre"
    BURNT_OAK = "barnet-burnt-oak-leisure-centre"

    @classmethod
    def display_name(cls, val):
        if val == cls.HENDON: return "Hendon Leisure Centre"
        if val == cls.COPTHALL: return "Barnet Copthall"
        if val == cls.BURNT_OAK: return "Barnet Burnt Oak"
        return val

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STOPPED = "STOPPED"

class LogLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"

# --- Models ---
@dataclass
class UserAccount:
    name: str
    email: str
    password_encrypted: str
    id: Optional[int] = None

@dataclass
class PaymentProfile:
    user_account_id: int
    alias: str
    cardholder_name: str
    card_number_encrypted: str
    expiry_month: str
    expiry_year: str
    cvv_encrypted: str
    address_line_1: str
    city: str
    postcode: str
    id: Optional[int] = None

@dataclass
class Task:
    user_account_id: int
    payment_profile_id: int
    leisure_centre: str
    target_date: str
    duration: int
    status: str
    last_checked_at: Optional[datetime] = None
    created_at: datetime = datetime.now()
    target_time_start: Optional[str] = None  # HH:MM string, e.g. "19:00"
    id: Optional[int] = None

@dataclass
class Booking:
    task_id: int
    reference_number: str
    court_name: str
    price: str
    booked_at: datetime = datetime.now()
    id: Optional[int] = None

@dataclass
class SystemLog:
    level: str
    source: str
    message: str
    task_id: Optional[int] = None
    timestamp: datetime = datetime.now()
    id: Optional[int] = None

# Create Tables
users = db.create(UserAccount)
payments = db.create(PaymentProfile)
tasks = db.create(Task)
bookings = db.create(Booking)
logs = db.create(SystemLog)

# --- App Setup ---
materialize_css = Link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css")
material_icons = Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons")
materialize_js = Script(src="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/js/materialize.min.js")
init_script = Script("""
document.addEventListener('DOMContentLoaded', function() {
    var elems = document.querySelectorAll('select');
    var instances = M.FormSelect.init(elems, {});
    var dates = document.querySelectorAll('.datepicker');
    var dateInstances = M.Datepicker.init(dates, {format: 'yyyy-mm-dd', autoClose: true});
    M.updateTextFields(); // Update labels for pre-filled inputs
});
""")

app, rt = fast_app(hdrs=(materialize_css, material_icons, materialize_js, init_script), pico=False)

# --- Components ---
def Layout(content):
    return Div(
        Nav(
            Div(
                A("Better Booking", href="/", cls="brand-logo left", style="padding-left: 20px;"),
                Ul(
                    Li(A("Dashboard", href="/")),
                    Li(A("Settings", href="/settings")),
                    Li(A("Logs", href="/logs")),
                    cls="right hide-on-med-and-down"
                ),
                cls="nav-wrapper teal lighten-1"
            )
        ),
        Div(content, cls="container section"),
    )

def UserRow(u):
    return Tr(
        Td(u.name),
        Td(u.email),
        Td(
            Form(
                Input(type="hidden", name="id", value=u.id),
                Button(I("delete", cls="material-icons"), cls="btn-flat red-text waves-effect", hx_delete=f"/users/{u.id}", hx_target="closest tr", hx_swap="outerHTML")
            )
        )
    )

def PaymentRow(p, u_name):
    return Tr(
        Td(p.alias),
        Td(u_name),
        Td(f"**** {decrypt_value(p.card_number_encrypted)[-4:]}"),
        Td(
            Form(
                Input(type="hidden", name="id", value=p.id),
                Button(I("delete", cls="material-icons"), cls="btn-flat red-text waves-effect", hx_delete=f"/payments/{p.id}", hx_target="closest tr", hx_swap="outerHTML")
            )
        )
    )

def TaskRow(t, u_name):
    status_color = "grey-text"
    if t.status == "SUCCESS": status_color = "green-text"
    elif t.status == "FAILED": status_color = "red-text"
    elif t.status == "RUNNING": status_color = "blue-text"
    
    time_pref = t.target_time_start if t.target_time_start else "Any"

    last_check_str = "-"
    if t.last_checked_at:
        if isinstance(t.last_checked_at, str):
            # Try parsing if it's a string, or just display it (maybe slice for HH:MM)
            try:
                # Assuming ISO format from DB
                dt = datetime.fromisoformat(t.last_checked_at)
                last_check_str = dt.strftime("%H:%M")
            except:
                last_check_str = t.last_checked_at[:16] # Fallback to raw string
        else:
            last_check_str = t.last_checked_at.strftime("%H:%M")

    return Tr(
        Td(LeisureCentre.display_name(t.leisure_centre)),
        Td(t.target_date),
        Td(time_pref),
        Td(f"{t.duration} min"),
        Td(u_name),
        Td(Strong(t.status, cls=status_color)),
        Td(last_check_str),
        Td(
            Form(
                Input(type="hidden", name="id", value=t.id),
                Button("Cancel", cls="btn-small red lighten-2", hx_delete=f"/tasks/{t.id}", hx_target="closest tr", hx_swap="outerHTML")
                if t.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value] else ""
            )
        )
    )

# --- Routes ---

@rt('/')
def get():
    all_tasks = tasks(order_by="created_at DESC")
    all_users = users()
    user_map = {u.id: u.name for u in all_users}
    
    task_rows = [TaskRow(t, user_map.get(t.user_account_id, "Unknown")) for t in all_tasks]
    active_count = len([t for t in all_tasks if t.status in ['PENDING', 'RUNNING']])

    return Main(
        Layout(
            Div(
                Div(
                    H4("Dashboard", cls="header"),
                    P(f"Active Tasks: {active_count}", cls="grey-text"),
                    cls="col s12"
                ),
                Div(
                    A(I("add", cls="material-icons left"), "Create New Task", href="/tasks/new", cls="btn teal waves-effect waves-light"),
                    cls="col s12", style="margin-bottom: 20px;"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("Location"), Th("Date"), Th("Start Time"), Th("Duration"), Th("User"), Th("Status"), Th("Last Check"), Th("Actions"))),
                        Tbody(*task_rows),
                        cls="highlight responsive-table"
                    ),
                    cls="card-panel"
                ),
                cls="row"
            )
        )
    )

@rt('/tasks/new')
def get():
    all_users = users()
    all_payments = payments()
    
    today = datetime.now().date()
    max_date = today + timedelta(days=7)
    
    # Generate time options (06:00 to 22:00)
    time_options = [Option("Any Time", value="")]
    for h in range(6, 23):
        for m in [0, 20, 40]: 
             t_str = f"{h:02}:{m:02}"
             time_options.append(Option(t_str, value=t_str))
    
    return Main(
        Layout(
            Div(
                H4("Create Booking Task", cls="header"),
                Form(
                    Div(
                        Div(
                            Select(
                                Option("Hendon Leisure Centre", value=LeisureCentre.HENDON.value),
                                Option("Barnet Copthall", value=LeisureCentre.COPTHALL.value),
                                Option("Barnet Burnt Oak", value=LeisureCentre.BURNT_OAK.value),
                                name="leisure_centre", required=True
                            ),
                            Label("Leisure Centre"),
                            cls="input-field col s12"
                        ),
                        cls="row"
                    ),
                    Div(
                        Div(
                            Input(type="text", cls="datepicker", name="target_date", required=True, value=str(today)),
                            Label("Target Date (Max 7 days ahead)"),
                            cls="input-field col s6"
                        ),
                        Div(
                            Select(*time_options, name="target_time_start"),
                            Label("Preferred Start Time (Optional)"),
                            cls="input-field col s6"
                        ),
                        cls="row"
                    ),
                    Div(
                        Div(
                            Select(
                                Option("40 Minutes", value="40"),
                                Option("60 Minutes", value="60"),
                                name="duration", required=True
                            ),
                            Label("Duration"),
                            cls="input-field col s12"
                        ),
                        cls="row"
                    ),
                    Div(
                        Div(
                            Select(
                                *[Option(u.name, value=u.id) for u in all_users],
                                name="user_account_id", required=True
                            ),
                            Label("Book As (User)"),
                            cls="input-field col s12"
                        ),
                        cls="row"
                    ),
                    Div(
                        Div(
                            Select(
                                *[Option(p.alias, value=p.id) for p in all_payments],
                                name="payment_profile_id", required=True
                            ),
                            Label("Payment Card"),
                            cls="input-field col s12"
                        ),
                        cls="row"
                    ),
                    Button(I("send", cls="material-icons right"), "Create Task", type="submit", cls="btn teal waves-effect waves-light"),
                    method="post", action="/tasks", cls="card-panel"
                )
            )
        )
    )

@rt('/tasks', methods=['POST'])
def post(leisure_centre: str, target_date: str, duration: int, user_account_id: int, payment_profile_id: int, target_time_start: str = None):
    tasks.insert(Task(
        leisure_centre=leisure_centre,
        target_date=target_date,
        duration=duration,
        user_account_id=user_account_id,
        payment_profile_id=payment_profile_id,
        status=TaskStatus.PENDING.value,
        target_time_start=target_time_start
    ))
    return RedirectResponse("/", status_code=303)

@rt('/tasks/{id}', methods=['DELETE'])
def delete(id: int):
    t = tasks[id]
    t.status = TaskStatus.STOPPED.value
    tasks.update(t)
    
    # Return updated row for HTMX swap
    all_users = users()
    user_map = {u.id: u.name for u in all_users}
    return TaskRow(t, user_map.get(t.user_account_id, "Unknown"))

@rt('/settings')
def get():
    all_users = users()
    all_payments = payments()
    user_rows = [UserRow(u) for u in all_users]
    user_map = {u.id: u.name for u in all_users}
    payment_rows = [PaymentRow(p, user_map.get(p.user_account_id, "Unknown")) for p in all_payments]

    return Main(
        Layout(
            Div(
                H4("Settings", cls="header"),
                
                # --- Users Section ---
                Div(
                    H5("User Accounts"),
                    Table(
                        Thead(Tr(Th("Name"), Th("Email"), Th("Actions"))),
                        Tbody(*user_rows),
                        cls="highlight"
                    ),
                    cls="card-panel"
                ),
                
                Div(
                    H6("Add User"),
                    Form(
                        Div(
                            Div(Input(name="name", type="text", cls="validate", required=True), Label("Display Name"), cls="input-field col s4"),
                            Div(Input(name="email", type="text", cls="validate", required=True), Label("Email/ID"), cls="input-field col s4"),
                            Div(Input(name="password", type="password", cls="validate", required=True), Label("Password"), cls="input-field col s4"),
                            cls="row"
                        ),
                        Button("Add User", type="submit", cls="btn-small teal"),
                        method="post", action="/users"
                    ),
                    cls="card-panel grey lighten-5"
                ),
                
                # --- Payments Section ---
                Div(
                    H5("Payment Profiles"),
                    Table(
                        Thead(Tr(Th("Alias"), Th("Linked User"), Th("Card End"), Th("Actions"))),
                        Tbody(*payment_rows),
                        cls="highlight"
                    ),
                    cls="card-panel"
                ),
                
                Div(
                    H6("Add Payment Profile"),
                    Form(
                        Div(
                            Div(
                                Select(
                                    *[Option(u.name, value=u.id) for u in all_users],
                                    name="user_account_id", required=True
                                ),
                                Label("Linked User"),
                                cls="input-field col s6"
                            ),
                            Div(Input(name="alias", type="text", cls="validate", required=True), Label("Alias"), cls="input-field col s6"),
                            cls="row"
                        ),
                        Div(
                            Div(Input(name="cardholder_name", type="text", cls="validate", required=True), Label("Cardholder Name"), cls="input-field col s6"),
                            Div(Input(name="card_number", type="text", cls="validate", required=True), Label("Card Number"), cls="input-field col s6"),
                            cls="row"
                        ),
                        Div(
                            Div(Input(name="expiry_month", type="text", cls="validate", required=True, maxlength=2), Label("MM"), cls="input-field col s4"),
                            Div(Input(name="expiry_year", type="text", cls="validate", required=True, maxlength=2), Label("YY"), cls="input-field col s4"),
                            Div(Input(name="cvv", type="text", cls="validate", required=True, maxlength=4), Label("CVV"), cls="input-field col s4"),
                            cls="row"
                        ),
                        H6("Billing Address"),
                        Div(
                            Div(Input(name="address_line_1", type="text", cls="validate", required=True), Label("Address Line 1"), cls="input-field col s12"),
                            cls="row"
                        ),
                        Div(
                            Div(Input(name="city", type="text", cls="validate", required=True), Label("City"), cls="input-field col s6"),
                            Div(Input(name="postcode", type="text", cls="validate", required=True), Label("Postcode"), cls="input-field col s6"),
                            cls="row"
                        ),
                        Button("Add Profile", type="submit", cls="btn-small teal"),
                        method="post", action="/payments"
                    ),
                    cls="card-panel grey lighten-5"
                )
            )
        )
    )

@rt('/users', methods=['POST'])
def post(name: str, email: str, password: str):
    users.insert(UserAccount(name=name, email=email, password_encrypted=encrypt_value(password)))
    return RedirectResponse("/settings", status_code=303)

@rt('/users/{id}', methods=['DELETE'])
def delete(id: int):
    users.delete(id)
    return ""

@rt('/payments', methods=['POST'])
def post(user_account_id: int, alias: str, cardholder_name: str, card_number: str, expiry_month: str, expiry_year: str, cvv: str, address_line_1: str, city: str, postcode: str):
    payments.insert(PaymentProfile(
        user_account_id=user_account_id, alias=alias, cardholder_name=cardholder_name,
        card_number_encrypted=encrypt_value(card_number), expiry_month=expiry_month, expiry_year=expiry_year,
        cvv_encrypted=encrypt_value(cvv), address_line_1=address_line_1, city=city, postcode=postcode
    ))
    return RedirectResponse("/settings", status_code=303)

@rt('/payments/{id}', methods=['DELETE'])
def delete(id: int):
    payments.delete(id)
    return ""

@rt('/logs')
def get():
    all_logs = logs(order_by="timestamp DESC", limit=100)
    log_rows = [Tr(Td(l.timestamp), Td(l.level), Td(l.source), Td(l.message)) for l in all_logs]
    return Main(Layout(Div(H4("System Logs", cls="header"), Table(Thead(Tr(Th("Time"), Th("Level"), Th("Source"), Th("Message"))), Tbody(*log_rows), cls="striped responsive-table card-panel"))))

if __name__ == "__main__":
    serve()
