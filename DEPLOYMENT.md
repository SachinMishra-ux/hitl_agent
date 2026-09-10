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

4. On the EC2 instance, inside the workspace directory created by the runner, create your `.env` file containing:
   ```env
   GOOGLE_API_KEY="<your-google-gemini-key>"
   LINKEDIN_ACCESS_TOKEN="<your-linkedin-token>"
   LINKEDIN_AUTHOR_URN="<your-linkedin-urn>"
   LINKEDIN_API_VERSION="202511"
   BASE_URL="http://<EC2-PUBLIC-IP>:8000"
   NOTIFICATION_EMAIL="sachin19566@gmail.com"
   # Optional SMTP credentials for real emails
   SMTP_HOST="smtp.gmail.com"
   SMTP_PORT=587
   SMTP_USER="<your-email>@gmail.com"
   SMTP_PASSWORD="<app-specific-password>"
   ```

---

## 3. GitHub Secrets Configuration

In your GitHub repository, go to **Settings** > **Secrets and variables** > **Actions** > **New repository secret**:

| Secret Name | Description | Example |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM User Access Key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | IAM User Secret Key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_DEFAULT_REGION` | AWS Region of ECR | `us-east-1` |
| `ECR_REPOSITORY_NAME` | Name of the ECR repo | `hitl-agent` |

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
