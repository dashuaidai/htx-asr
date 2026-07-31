# Task 6 — Step-by-step AWS deployment guide

Deploys the Task 3 architecture: one EC2 VM running the 2-node Elasticsearch
cluster (`elastic-backend/`) and the Search-UI frontend (`search-ui/`) as
self-managed Docker containers. No managed services are used.

Estimated time: 20–30 minutes. Estimated cost: $0 on the free tier
(t2.micro/t3.micro, 750 h/month) — a t3.medium (~USD 0.05/h) gives a snappier
demo if you don't mind a few dollars.

## 1. Launch the EC2 instance

AWS Console → EC2 → **Launch instance**:

1. Name: `htx-search`
2. AMI: **Amazon Linux 2023** (x86_64)
3. Instance type: `t3.medium` (recommended) or `t2.micro`/`t3.micro` (free tier —
   works thanks to the swap file `setup-ec2.sh` creates, but slower)
4. Key pair: create/download one (e.g. `htx-key.pem`)
5. Network settings → **Edit**:
   - Auto-assign public IP: **Enable**
   - Security group rules:
     | Type | Port | Source | Purpose |
     |---|---|---|---|
     | SSH | 22 | *My IP* | admin access |
     | Custom TCP | 3000 | 0.0.0.0/0 | public Search-UI |
     (ports 9200/9300 are deliberately **not** opened)
6. Storage: 20 GiB gp3
7. **Launch instance**, then note its **public IPv4 address**.

Optional but recommended: EC2 → Elastic IPs → Allocate → Associate with the
instance, so the URL survives instance restarts.

## 2. Prepare the host

```bash
ssh -i htx-key.pem ec2-user@<EC2-IP>

git clone https://github.com/<your-username>/htx-asr.git
cd htx-asr
bash deploy/setup-ec2.sh        # docker, compose, vm.max_map_count, 4 GB swap
exit                            # log out & back in so 'docker' works without sudo
```

## 3. Start the stack

```bash
ssh -i htx-key.pem ec2-user@<EC2-IP>
cd htx-asr
bash deploy/deploy.sh           # starts es01+es02, waits for health, builds+starts search-ui
```

## 4. Index the data

From your laptop, upload the CSV produced in Task 2d, then index it on the instance:

```bash
scp -i htx-key.pem /path/to/common_voice/cv-valid-dev.csv ec2-user@<EC2-IP>:~/
ssh -i htx-key.pem ec2-user@<EC2-IP>
cd htx-asr && bash deploy/index-data.sh ~/cv-valid-dev.csv   # -> count: 4076
```

## 5. Verify (Task 7)

Open **http://\<EC2-IP\>:3000** in a browser — search and facet filters should
work. Put this URL into the root `README.md` (Deployment URL section).

## Troubleshooting

- `es01`/`es02` exit with code 137 → not enough memory: confirm the swap file
  is active (`swapon --show`), or lower `ES_JAVA_OPTS` to `-Xms256m -Xmx256m`
  in `elastic-backend/docker-compose.yml`.
- `max virtual memory areas vm.max_map_count [65530] is too low` →
  `sudo sysctl -w vm.max_map_count=262144` (setup-ec2.sh already persists this).
- Search-UI loads but shows no results → the index is empty; run step 4.
- Browser can't reach port 3000 → check the security group inbound rule and
  that you're using `http://` (not `https://`).

## Undeploying (after submission is confirmed — Task 9)

EC2 → select instance → Instance state → **Terminate**; release the Elastic IP
if you allocated one (idle EIPs incur charges).
