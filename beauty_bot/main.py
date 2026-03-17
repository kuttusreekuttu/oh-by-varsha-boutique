from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import mysql.connector
import shutil
import uuid
import re

app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

PUBLIC_URL = "https://examine-twiki-translated-computational.trycloudflare.com/static/"


# ---------------- DATABASE ----------------

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sree@123",
        database="boutique"
    )


# ---------------- USER MEMORY ----------------

user_state = {}


@app.get("/")
def home():
    return {"message": "Bot Running"}


# ---------------- CATALOGUE ----------------

@app.get("/catalogue", response_class=HTMLResponse)
def catalogue(request: Request):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM dresses ORDER BY display_order ASC")
    dresses = cursor.fetchall()

    cursor.close()
    db.close()

    return templates.TemplateResponse(
        "catalogue.html",
        {"request": request, "dresses": dresses}
    )


# ---------------- DASHBOARD ----------------

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM dresses ORDER BY display_order ASC")
    dresses = cursor.fetchall()

    cursor.execute("""
    SELECT o.*, d.image_url
    FROM orders o
    JOIN dresses d ON o.dress_id = d.dress_id
    ORDER BY o.order_date DESC
    """)

    orders = cursor.fetchall()

    cursor.close()
    db.close()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "dresses": dresses,
            "orders": orders
        }
    )


# ---------------- ADD DRESS ----------------

@app.post("/add_dress")
async def add_dress(
    dress_id: str = Form(...),
    dress_name: str = Form(...),
    price: int = Form(...),
    stock: int = Form(...),
    display_order: int = Form(...),
    image: UploadFile = File(...)
):

    filename = str(uuid.uuid4()) + ".jpg"
    filepath = f"static/{filename}"

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    image_url = PUBLIC_URL + filename

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    INSERT INTO dresses (dress_id,dress_name,price,image_url,display_order)
    VALUES(%s,%s,%s,%s,%s)
    """, (dress_id, dress_name, price, image_url, display_order))

    cursor.execute("""
    INSERT INTO dress_variants
    (variant_id,dress_id,color,size,stock)
    VALUES(%s,%s,%s,%s,%s)
    """, (dress_id + "V1", dress_id, "Default", "OneSize", stock))

    db.commit()

    cursor.close()
    db.close()

    return RedirectResponse("/dashboard", status_code=303)


# ---------------- DELETE DRESS ----------------

@app.get("/delete_dress/{dress_id}")
def delete_dress(dress_id: str):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM dresses WHERE dress_id=%s", (dress_id,))
    cursor.execute("DELETE FROM dress_variants WHERE dress_id=%s", (dress_id,))

    db.commit()

    cursor.close()
    db.close()

    return RedirectResponse("/dashboard", status_code=303)


# ---------------- EDIT DRESS ----------------

@app.get("/edit_dress/{dress_id}", response_class=HTMLResponse)
def edit_dress(request: Request, dress_id: str):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM dresses WHERE dress_id=%s", (dress_id,))
    dress = cursor.fetchone()

    cursor.close()
    db.close()

    return templates.TemplateResponse(
        "edit_dress.html",
        {"request": request, "dress": dress}
    )


@app.post("/update_dress")
async def update_dress(
    dress_id: str = Form(...),
    dress_name: str = Form(...),
    price: int = Form(...),
    display_order: int = Form(...)
):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    UPDATE dresses
    SET dress_name=%s, price=%s, display_order=%s
    WHERE dress_id=%s
    """, (dress_name, price, display_order, dress_id))

    db.commit()

    cursor.close()
    db.close()

    return RedirectResponse("/dashboard", status_code=303)


# ---------------- WHATSAPP BOT ----------------

@app.post("/whatsapp")
async def whatsapp(
    From: str = Form(...),
    Body: str = Form(...)
):

    msg = Body.strip()
    msg_upper = msg.upper()

    if From not in user_state:
        user_state[From] = {}

    state = user_state[From]

    hi_detect = msg_upper.startswith("HI")
    dress_match = re.search(r"D\d+", msg_upper)
    order_match = re.search(r"ORDER\s*(D\d+)", msg_upper)

    # START MENU
    if hi_detect:

        state.clear()

        reply = """Welcome to Oh By Varsha 🌸

1 Order Dress
2 View Catalogue"""

    # OPTION 1
    elif msg_upper == "1":

        state["step"] = "waiting_dress"

        reply = """Please send Dress ID to order.

Example:
D101"""

    # OPTION 2
    elif msg_upper == "2":

        reply = "View Catalogue:\nhttps://examine-twiki-translated-computational.trycloudflare.com/catalogue"

    # ORDER FROM CATALOGUE
    elif order_match:

        dress_id = order_match.group(1)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM dresses WHERE dress_id=%s",
            (dress_id,)
        )

        dress = cursor.fetchone()

        cursor.close()
        db.close()

        if not dress:
            reply = "Dress not found"

        else:

            state["dress"] = dress_id
            state["step"] = "ask_details"

            xml = "<Response>"
            xml += "<Message>"
            xml += f"<Body>{dress['dress_name']} - ₹{dress['price']}\n\n📦 Please send delivery details\n\nExample:\nSreekutty, Kochi</Body>"
            xml += f"<Media>{dress['image_url']}</Media>"
            xml += "</Message>"
            xml += "</Response>"

            return Response(xml, media_type="application/xml")

    # DIRECT DRESS ID
    elif dress_match:

        dress_id = dress_match.group()

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM dresses WHERE dress_id=%s",
            (dress_id,)
        )

        dress = cursor.fetchone()

        cursor.close()
        db.close()

        if not dress:
            reply = "Dress not found"

        else:

            state["dress"] = dress_id
            state["step"] = "ask_details"

            xml = "<Response>"
            xml += "<Message>"
            xml += f"<Body>{dress['dress_name']} - ₹{dress['price']}\n\n📦 Please send delivery details\n\nExample:\nSreekutty, Kochi</Body>"
            xml += f"<Media>{dress['image_url']}</Media>"
            xml += "</Message>"
            xml += "</Response>"

            return Response(xml, media_type="application/xml")

    # CUSTOMER DETAILS
    elif state.get("step") == "ask_details":

        if "," not in msg:

            reply = "Please send details like:\n\nAnu, 5/102, Puthenpally, Thrissur – 680001"

            return Response(
                f"<Response><Message>{reply}</Message></Response>",
                media_type="application/xml"
            )

        name, address = msg.split(",", 1)
        name = name.strip()
        address = address.strip()

        phone = From.replace("whatsapp:", "")
        dress_id = state["dress"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
        INSERT INTO orders
        (dress_id,color,size,customer_name,address,city,phone,payment_method,order_status)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'Pending')
        """, (dress_id, "Default", "OneSize", name, address, "", phone, "Cash on Delivery"))

        cursor.execute("""
        UPDATE dress_variants
        SET stock = stock - 1
        WHERE dress_id = %s
        """, (dress_id,))

        db.commit()

        cursor.close()
        db.close()

        reply = f"""✅ Order Confirmed!

Dress: {dress_id}
Name: {name}
Address: {address}

Our team will contact you soon."""

        user_state.pop(From)

    else:

        reply = "Send HI to start"

    return Response(
        f"<Response><Message>{reply}</Message></Response>",
        media_type="application/xml"
    )

