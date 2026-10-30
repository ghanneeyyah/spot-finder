"""Local demo server for manual curl testing. NEVER deploy this.

It runs the real FirebaseTokenVerifier, but trusts a throwaway certificate generated at startup
instead of Google's, so it can mint its own tokens. Tokens are written to $DEMO_TOKEN_DIR
(default .demo_tokens, which is git-ignored).
"""

import os
from pathlib import Path

from app.config import Settings
from app.main import create_app
from app.middleware.rate_limit import Rule
from app.services.firebase_auth import FirebaseTokenVerifier

from tests.conftest import FakeUploader
from tests.helpers import certs_client, make_signing_material, mint_token

PROJECT = "demo-project"
material = make_signing_material()

token_dir = Path(os.environ.get("DEMO_TOKEN_DIR", ".demo_tokens"))
token_dir.mkdir(parents=True, exist_ok=True)
tokens = {
    "alice": mint_token(material, project_id=PROJECT, uid="demo-alice", email="alice@example.com"),
    "bob": mint_token(material, project_id=PROJECT, uid="demo-bob"),
    "mod": mint_token(material, project_id=PROJECT, uid="demo-mod"),
    "expired": mint_token(material, project_id=PROJECT, uid="demo-alice", expires_in=-3600),
    "wrong_audience": mint_token(material, project_id=PROJECT, audience="another-project"),
}
for name, value in tokens.items():
    (token_dir / name).write_text(value)

app = create_app(
    Settings(
        database_url=os.environ["DATABASE_URL"],
        environment="development",
        firebase_project_id=PROJECT,
        cloudinary_cloud_name="democloud",
        cors_origins=["http://localhost:3000"],
    ),
    token_verifier=FirebaseTokenVerifier(PROJECT, http=certs_client(material)),
    uploader=FakeUploader(),
    rate_limit_overrides={("POST", "/api/spots"): Rule(8, 60)},
)
