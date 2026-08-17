# Canon Cloud (optional)

Local Canon does not need this. Cloud is sync + seats + billing.

Stripe is **not** used. New Stripe accounts in India are invite-only.
Payments go through [Polar.sh](https://polar.sh) (merchant of record).

## What you run

```bash
pip install "canon-memory[server]"
export CANON_CLOUD_OPEN_SYNC=1   # skip billing while you dogfood
python -m canon.server
```

On another machine (or the same one):

```bash
export CANON_CLOUD_URL=http://127.0.0.1:8787
canon cloud login
canon cloud push
canon cloud pull
```

## What you must set up (once)

### 1. Polar (payments)

1. Create an account at https://polar.sh (works if Stripe India does not).
2. Create two products: **Canon Pro** and **Canon Team** (monthly).
3. Suggested prices from the original plan: Pro ~$15/user/month, Team ~$39/user/month. You pick the number.
4. Copy each product id.
5. Create an organization access token.
6. Add a webhook to `https://YOUR_HOST/v1/billing/polar` for subscription/checkout events.
7. Copy the webhook secret.

### 2. Host the API

Railway, Render, or Fly. Dockerfile is in the repo root.

Required env:

```text
CANON_CLOUD_PUBLIC_URL=https://YOUR_HOST
CANON_CLOUD_HOST=0.0.0.0
PORT=8787
CANON_CLOUD_DB=/data/cloud.db
```

For paid sync (turn off open mode):

```text
CANON_CLOUD_OPEN_SYNC=0
POLAR_ACCESS_TOKEN=polar_oat_...
POLAR_PRODUCT_PRO=prod_...
POLAR_PRODUCT_TEAM=prod_...
POLAR_WEBHOOK_SECRET=whsec_...
POLAR_SUCCESS_URL=https://YOUR_HOST/paid
```

### 3. Point the CLI at it

Users set:

```text
CANON_CLOUD_URL=https://YOUR_HOST
```

Then `canon cloud login` and `canon cloud upgrade pro`.

## Plans

| Plan | Seats | Sync |
| --- | --- | --- |
| free (no Polar) | 0 | no, unless `CANON_CLOUD_OPEN_SYNC=1` |
| pro | 5 | yes |
| team | 25 | yes |

## Privacy

Snapshots are the same JSON as `canon export`. No GitHub tokens. No source code.
Turn Polar off and keep `CANON_CLOUD_OPEN_SYNC=1` for a private team server.
