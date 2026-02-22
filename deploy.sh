source ./.env

uv lock
uv export --format requirements-txt --no-hashes --no-dev --no-emit-project -o src/requirements.txt

CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.11
gcloud -q components update
gcloud -q functions deploy ${FUNCTION_NAME} \
	--gen2 \
	--region=asia-northeast1 \
	--runtime=python311 \
	--trigger-http \
	--allow-unauthenticated \
	--timeout=5s \
	--min-instances=0 \
	--max-instances=10 \
	--memory=256Mi \
	--source=src/ \
	--entry-point=main \
	--service-account ${SERVICE_ACCOUNT} \
