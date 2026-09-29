# UP! | Mountain Hiking Platform

A multilingual Django hiking platform with worldwide peak search, OpenStreetMap trail maps, coordinate-based weather, equipment planning, a floating hiking assistant and a community story feed.

## Requirements

- Python 3.10 or newer
- pip
- Redis only when using `REDIS_URL` for a shared production cache
- Internet access for external maps, mountain search, photos, fonts and icons. Weather/search API credentials are configured separately below.

## Install and run

Open a terminal in the extracted `mountain_hiking_platform` folder:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. SQLite is configured by default and `db.sqlite3` is created by migrations.

On macOS/Linux, activate the environment with `source venv/bin/activate` and copy the example file with `cp .env.example .env`.

## Demo accounts

The seed command creates five community authors, each with the password `tau-demo-2026`:

- `Aida`
- `Timur`
- `Mira`
- `Daniyar`
- `Alina`

Use one to try saved routes, the personal equipment checklist, likes, comments and profile editing. These accounts and passwords are sample data for local development only.

## Languages

Russian is the default language. The RU / KZ / EN selector changes the shared interface language to Russian, Kazakh or English. The selector uses Django's language session and locale middleware; interface strings are centralized in `core/context_processors.py`. Model content and seeded route names are shared across languages. Django's standard translation catalogs can be added under `locale/` for further translated model content.

## Demo data

`python manage.py seed_data` is safe to run more than once. It creates eight mountain routes, eighteen equipment items, five hiking stories and sample comments. Demo images are sourced from Unsplash URLs and are not stored locally.

## Environment and integrations

Copy `.env.example` to `.env`. Keep real secrets out of source control.

- `SECRET_KEY`: Django secret key. Replace the development value for deployment.
- `DEBUG`: use `False` in production and configure production hosts, HTTPS, static files and a production database before deploying.
- `AI_API_KEY`: optional bearer API key for an OpenAI-compatible chat-completions endpoint. Without it, the assistant gives deterministic local recommendations in the selected language.
- `AI_API_URL`: optional chat-completions endpoint; defaults to the OpenAI API URL.
- `AI_MODEL`: optional model name; defaults to `gpt-6-luna`.
- `WEATHER_API_KEY`: OpenWeather API key. Without it, the weather component clearly reports that live conditions are unavailable; it does not display sample weather.
- `WEATHER_API_URL` / `WEATHER_FORECAST_API_URL`: optional OpenWeather endpoint overrides.
- `MOUNTAIN_SEARCH_URL`: Nominatim-compatible global peak search endpoint. Public Nominatim requires no API key.
- `MOUNTAIN_SEARCH_USER_AGENT`: identifying application name for Nominatim and Overpass requests. Set a real project name and contact before public deployment.
- `MOUNTAIN_SEARCH_CONTACT`: optional contact email sent to Nominatim.
- `OVERPASS_API_URL`: Overpass endpoint used for actual OSM trail geometry.
- `MAP_TILE_URL` / `MAP_TILE_ATTRIBUTION`: configurable Leaflet tile layer and required attribution.
- `MAP_TILE_URL` uses Leaflet's `{z}`, `{x}`, and `{y}` placeholders. The default OpenStreetMap tile layer requires no key; a commercial tile provider can be configured here.
- `REDIS_URL`: optional Redis connection URL. Use shared Redis in a multi-worker deployment so provider caching and public-service rate limits are shared across workers.
- `DATABASE_URL`: PostgreSQL connection URL. Required when `DEBUG=False`; Vercel's function filesystem is not a persistent SQLite database.
- `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: S3-compatible media storage for persistent story-photo uploads. Optional `AWS_S3_ENDPOINT_URL` and `AWS_S3_CUSTOM_DOMAIN` support S3-compatible providers.
- `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`: comma-separated production domains and trusted HTTPS origins.

AI requests are made in `ai_assistant/services.py`; weather requests are made in `weather/services.py`. Seeded routes use their stored approximate coordinates; globally searched peaks use Nominatim coordinates for weather and mapped OpenStreetMap trails. Weather never substitutes sample conditions: without a key or during an upstream failure, the interface explains what is unavailable. The AI still offers gear advice without a key and explicitly says when live weather context is missing.

The map, worldwide peak search and trail geometry use OpenStreetMap services with visible attribution. Nominatim's public service is rate-limited and requires an identifying User-Agent; configure `MOUNTAIN_SEARCH_USER_AGENT` and `MOUNTAIN_SEARCH_CONTACT`, keep autocomplete enabled only with the built-in debounce, and use a hosted/commercial provider for sustained production traffic. OpenStreetMap's public tile service is not an offline or bulk-tile source. For deployment, configure a shared Redis cache, set strong secrets and allowed hosts, then run `python manage.py collectstatic` as part of the release process.

## Deploy to Vercel

Vercel currently detects Django from `manage.py`, uses `config/wsgi.py`, and collects `STATIC_ROOT` automatically. `vercel.json` only raises the WSGI function duration for the external map/weather requests; no custom build command or route rewrite is needed.

1. Create a managed PostgreSQL database (for example, Neon) and an S3-compatible bucket for story-photo uploads. A Vercel function's local filesystem is temporary, so the project intentionally refuses to use SQLite for production.
2. Import the repository into Vercel and add these Project Environment Variables for Production (and Preview if needed): `SECRET_KEY` (generate a new long random value), `DEBUG=False`, `DATABASE_URL`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `WEATHER_API_KEY`, `AI_API_KEY`, `MOUNTAIN_SEARCH_USER_AGENT`, `MOUNTAIN_SEARCH_CONTACT`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`. Add `REDIS_URL` if you want shared cross-function cache/rate limits. Do not upload `.env` or put credentials in `vercel.json`.
3. Set `ALLOWED_HOSTS` to the Vercel hostname/custom domains and `CSRF_TRUSTED_ORIGINS` to their `https://` origins. Vercel's `VERCEL_URL` is added automatically for preview deployments.
4. Deploy with the Vercel Git integration or `vercel deploy`. Vercel detects the WSGI application, builds static assets, and serves them through its CDN.
5. Initialize the database once from a trusted terminal with the Production Vercel environment loaded: run `vercel env pull .env.local`, then `python manage.py migrate`. Run `python manage.py seed_data` only if you want the sample hiking content in that database.

For local commands against the Vercel database, the settings load `.env.local`; it is ignored by Git. Use a pooled PostgreSQL URL if the database provider offers one. Media uploads require the configured S3 bucket; without a bucket, local development uses `media/` on disk.

## Useful commands

```powershell
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data
python manage.py test tests
python manage.py createsuperuser
python manage.py runserver
```

Visit `/admin/` after creating a superuser to manage mountains, equipment, saved routes, checklist records, stories and comments.

## Project map

```text
config/          Django settings, root URLs and ASGI/WSGI entry points
accounts/        Profile, registration, sign in and profile editing
mountains/       Routes, equipment, saved hikes and preparation checklist
community/       Hiking stories, image uploads, comments and likes
weather/         Coordinate-based OpenWeather API and forecast endpoints
ai_assistant/    Floating chat endpoint, assistant page and recommendation adapter
mountains/services.py  Nominatim worldwide peak search and Overpass trail geometry
core/            Home page, shared translations and template filters
templates/       Shared layout and page templates
static/          Responsive stylesheet and small UI interactions
media/           Uploaded story-cover images
locale/          Django message-catalog directory
```

## Notes

- Story cover uploads are stored under `media/stories/` during local development.
- Photos, Google Fonts and Lucide icons are external resources. Internet access is needed to display these assets; the source project includes image fallbacks as URL-based demo records.
- This is a prototype, not a safety authority. Confirm route access and conditions with local guides and rescue services before hiking.
