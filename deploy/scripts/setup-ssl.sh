#!/usr/bin/env bash
# Setup SSL certificates for windyclone.ai using Let's Encrypt.
# Run on the VPS (72.60.118.54) with root access.
#
# windyclone.com is NOT issued a cert here — it 302-redirects to
# windyclone.ai at the Cloudflare page-rule level, so traffic for the
# legacy domain never terminates TLS on this box.

set -euo pipefail

DOMAIN="windyclone.ai"
EMAIL="grant@windypro.com"

echo "🔐 Setting up SSL for $DOMAIN..."

# Install certbot if not present
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
fi

# Stop nginx temporarily for standalone verification
systemctl stop nginx 2>/dev/null || true

# Get certificate
certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

# Restart nginx
systemctl start nginx

# Set up auto-renewal cron
echo "Setting up auto-renewal..."
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | sort -u | crontab -

echo "✅ SSL setup complete for $DOMAIN"
echo "   Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "   Key:         /etc/letsencrypt/live/$DOMAIN/privkey.pem"
