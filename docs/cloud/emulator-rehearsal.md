# Local AWS Emulator rehearsal

The local rehearsal passed on 16 November 2026 using AWS Emulator 1.0.385 and
34 loopback SDK requests. No real AWS request, Terraform apply or model call
was made. The original Kubernetes cluster stayed stopped. The owned emulator
container and generated session credentials were removed.

## What was tested

- Actual Secrets Manager helpers created two tagged application/migration
  credentials, resumed them without password rotation, and deleted them.
- S3 versioned object round-trip and a rejected conditional lock collision.
- Cleanup of all emulated objects and private session files.
- Endpoint guards reject external hosts, plaintext and unexpected ports.

This tests API serialization and application reconciliation. It does not prove
Terraform deployment, IAM, bucket policies, EKS, RDS failover, network controls,
service quotas or billing. AWS explicitly excludes security assurance from the
emulator; see [AWS security guidance](https://docs.aws.amazon.com/emulator/latest/userguide/security.html).

## Reproduce only when needed

The reviewed package, base image, SDK versions, hashes and publisher fingerprint
are in `infra/emulator/toolchain.json`. Download only those exact versions.
Never use real AWS credentials, the operator profile or real customer data.
The runner strips provider/AWS environment variables, uses fresh local credentials
and CA verification, disables telemetry/retries/proxies, limits local SDK requests
to 100 and accepts only `https://127.0.0.1:9297`.

PowerShell, from the repository root, with Docker running:

```powershell
$package = '.runtime/verification/cloud/emulator/package'
New-Item -ItemType Directory -Force $package | Out-Null
$lock = Get-Content infra/emulator/toolchain.json -Raw | ConvertFrom-Json
Invoke-WebRequest $lock.package.source -OutFile "$package/aws-emulator.rpm"
Invoke-WebRequest $lock.signature.source -OutFile "$package/aws-emulator.rpm.sig"
Invoke-WebRequest 'https://downloads.aws.com/keys/gpg/current.asc' -OutFile "$package/aws-publishing.asc"
if ((Get-FileHash "$package/aws-emulator.rpm" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $lock.package.sha256) { throw 'Package hash mismatch' }
if ((Get-FileHash "$package/aws-emulator.rpm.sig" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $lock.signature.sha256) { throw 'Signature hash mismatch' }
```

With GnuPG available, use a dedicated keyring (Git for Windows also supplies
`C:/Program Files/Git/usr/bin/gpg.exe`). From the package directory, run:

```sh
mkdir gnupg
gpg --homedir ./gnupg --import aws-publishing.asc
gpg --homedir ./gnupg --fingerprint ssm-publishing@amazon.com
gpg --homedir ./gnupg --status-fd 1 --verify aws-emulator.rpm.sig aws-emulator.rpm
```

Require fingerprint `98BCF336A3BE53B734E967C52E5BF49BD940F624`, a good signature,
and matching VALIDSIG fingerprint before building. Stop on a mismatch. These
follow [AWS package verification](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-linux.html).
Use an empty dedicated directory when reproducing; preserve earlier receipts.

Back at the repository root:

```powershell
Copy-Item infra/emulator/Dockerfile "$package/Dockerfile"
docker build --platform linux/amd64 -t opsproof-emulator:1.0.385 $package
uv venv .runtime/cloud/sdk --python 3.14
uv pip install --python .runtime/cloud/sdk/Scripts/python.exe 'boto3==1.44.3' 'botocore==1.44.3'
& '.runtime/cloud/sdk/Scripts/python.exe' -m scripts.cloud.validate_emulator --execute
```

The dedicated build directory should contain only the public package, signature,
public key, Dockerfile and verification receipts/keyring; add a `.dockerignore`
allowing only Dockerfile and aws-emulator.rpm to the context. The runtime is
nonroot/read-only with a private session bind, 2 GiB/one CPU and loopback-only
port publication. It mounts neither real AWS files nor the Docker socket.
Do not point Terraform's actual platform provider at this emulator.

Retained proof: `.runtime/verification/cloud/emulator/package/signature-verification.json`
and `.runtime/verification/cloud/emulator/run-8c682ff080704a839a992d32bc5472f4/result.json`.
A failed earlier asynchronous deletion attempt is also retained; the passing run
uses bounded deletion polling and preserves unknown outcomes as failures.
