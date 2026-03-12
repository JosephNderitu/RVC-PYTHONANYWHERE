````markdown
# Django Project Setup

Follow the steps below to set up and run the project locally.

---

## 1. Clone the Repository

```bash
git clone <repository-url>
cd <project-folder>
````

---

## 2. Create Virtual Environment

```bash
python -m venv venv
```

---

## 3. Activate Virtual Environment

**Windows**

```bash
venv\Scripts\activate
```

**Mac/Linux**

```bash
source venv/bin/activate
```

---

## 4. Install Dependencies

Install packages from `requirements.txt`.

```bash
pip install -r requirements.txt
```

If new dependencies are added, update the file using:

```bash
pip freeze > requirements.txt
```

---

## 5. Ensure You Are in the Correct Directory

Before running Django commands, confirm you are inside the directory containing `manage.py`.

Example:

```bash
ls
```

You should see:

```
manage.py
```

---

## 6. Run Database Migrations

```bash
python manage.py migrate
```

---

## 7. Create Admin Superuser

```bash
python manage.py createsuperuser
```

Follow the prompts to set username, email, and password.

---

## 8. Run the Development Server

```bash
python manage.py runserver
```

The application will be available at:

```
http://127.0.0.1:8000/
```

Admin panel:

```
http://127.0.0.1:8000/admin/
```

---

## Support

If you encounter any issues during setup or running the project, contact:

**Joseph Gikuru**
📧 [gikurujoseph53@gmail.com](mailto:gikurujoseph53@gmail.com)

```
```
