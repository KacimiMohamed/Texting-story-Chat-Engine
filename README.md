# Texting Story (Django)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run migrations:
   - `python manage.py migrate`
4. Create an admin user:
   - `python manage.py createsuperuser`
5. Start the server:
   - `python manage.py runserver`
6. Open admin:
   - `http://127.0.0.1:8000/admin/`

## Data model

- `Character`: name, color, avatar image.
- `Story`: title, background color, optional character cast.
- `Message`: belongs to a story and character, includes text/image, delay, and order.

In the admin panel, open a `Story` and add all message lines inline in sequence.
