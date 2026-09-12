# AWS Deployment Guide for HITL LinkedIn Agent

This guide outlines the steps to deploy the **Human-in-the-Loop (HITL) LinkedIn Agent** to AWS using **Amazon Elastic Container Registry (ECR)** and an **Amazon EC2** instance with automated GitHub Actions CI/CD.

---

## 1. Prerequisites on AWS

1. **AWS Account & IAM User**:
   - Create an IAM user with programmatic access (`AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`).
   - Attach policies:
     - `AmazonEC2ContainerRegistryFullAccess` (for pushing/pulling from ECR)
     - `AmazonEC2FullAccess` (or sufficient EC2 privileges)

2. **Amazon ECR Repository**:
   - Create an ECR repository named `hitl-agent` in your desired AWS Region (e.g. `us-east-1` or `ap-south-1`):
     ```bash
     aws ecr create-repository --repository-name hitl-agent --region <your-region>
     ```

3. **Amazon EC2 Instance**:
   - Launch an Ubuntu 22.04 / 24.04 LTS instance (e.g., `t3.medium` or `t3.small`).
   - Configure Security Group:
     - Allow Inbound **Port 22** (SSH) from your IP.
     - Allow Inbound **Port 8000** (or Port 80/443 if using Nginx/Reverse Proxy).
   - SSH into the EC2 instance and install Docker:
     ```bash
     sudo apt-get update
     sudo apt-get install -y docker.io docker-compose curl
     sudo usermod -aG docker ubuntu
     newgrp docker
     ```

---

## 2. Setting Up GitHub Actions Self-Hosted Runner on EC2

To enable zero-downtime automated deployment on `git push main`:

1. In your GitHub repository, navigate to **Settings** > **Actions** > **Runners** > **New self-hosted runner**.
2. Select **Linux** and **ARM64 / x64** depending on your EC2 instance architecture.
3. Follow the instructions to download and configure the runner on your EC2 instance:
   ```bash
   mkdir actions-runner && cd actions-runner
   # Download runner package (URLs provided by GitHub)
   curl -o actions-runner-linux.tar.gz -L <GITHUB_RUNNER_DOWNLOAD_URL>
   tar xzf ./actions-runner-linux.tar.gz
   ./config.sh --url https://github.com/SachinMishra-ux/hitl_agent --token <RUNNER_TOKEN>
   sudo ./svc.sh install
   sudo ./svc.sh start
   ```

> [!NOTE]
> You **do not** need to manually create or manage a `.env` file on the EC2 host. The deployment pipeline dynamically generates the `.env` file directly from your GitHub Secrets during CI/CD execution and secures its permissions (`chmod 600`).

---

## 3. GitHub Secrets Configuration

In your GitHub repository, navigate to **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.

### A. Required AWS Secrets (for CI/CD pipeline)

| Secret Name | Description | Example |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM User Access Key with ECR permissions | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | IAM User Secret Access Key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` *(or `AWS_DEFAULT_REGION`)* | AWS Region where your ECR is located | `us-east-1` (or `ap-south-1`) |
| `ECR_REPOSITORY_NAME` | Name of your ECR repository | `hitl-agent` |

### B. Application Environment Secrets (Choose Option 1 or Option 2)

#### Option 1: Single `ENV_FILE` Secret (Recommended & Fastest)
Create a single repository secret named **`ENV_FILE`** and paste your entire `.env` content directly:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
LINKEDIN_ACCESS_TOKEN=your_linkedin_access_token_here
LINKEDIN_AUTHOR_URN=urn:li:person:xxxxxxxxxx
LINKEDIN_API_VERSION=202511
BASE_URL=http://<YOUR_EC2_PUBLIC_IP>:8000
NOTIFICATION_EMAIL=your_email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_google_app_password
```

#### Option 2: Individual Secrets
If you prefer managing each secret individually, you can set the following secrets in GitHub:

| Secret Name | Description | Default if omitted |
|---|---|---|
| `GOOGLE_API_KEY` | Google Gemini API Key | *(Required)* |
| `GEMINI_MODEL` | Gemini LLM model | `gemini-2.5-flash` |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn OAuth Bearer Token (Community Management API) | *(Required)* |
| `LINKEDIN_AUTHOR_URN` | LinkedIn Author URN (`urn:li:person:...`) | *(Required)* |
| `LINKEDIN_API_VERSION` | LinkedIn REST API Version | `202511` |
| `BASE_URL` | Public URL for approval callback links | `http://localhost:8000` (set to `http://<EC2_IP>:8000`) |
| `NOTIFICATION_EMAIL` | Destination email for approval requests | `sachin19566@gmail.com` |
| `SMTP_HOST` | SMTP server host | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username / email address | e.g. `sachin19566@gmail.com` |
| `SMTP_PASSWORD` | SMTP password / Google App Password (16 chars) | e.g. `xxxx xxxx xxxx xxxx` |

---

## 4. Persistent Storage (EBS / Directory)

The Human-in-the-Loop approval workflow allows human reviewers to take **1 to 7+ days** to approve posts. The SQLite checkpointer saves all workflow checkpoints to `./data/checkpoints.db`.

In the `deploy.yml` and `docker-compose.yml`, the volume `-v $(pwd)/data:/app/data` ensures that:
- Checkpoints and thread states survive container restarts and image updates.
- If a post was drafted 5 days ago, the human reviewer can still click the review link or approve button and the agent will resume right where it paused.

---

## 5. Local Docker Testing

To test the container build locally before deploying:

```bash
# Build and run with docker-compose
docker-compose up --build -d

# Check logs
docker-compose logs -f

# Verify health endpoint
curl http://localhost:8000/api/health
```
