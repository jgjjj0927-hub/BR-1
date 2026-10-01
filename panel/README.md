# BR Panel

## Установка на VPS

```bash
# Скопировать папку panel/ на сервер
scp -r panel/ root@br-v2.ru:/root/panel

# На сервере
cd /root/panel
npm install

# Получить serviceAccount.json:
# Firebase Console → Project Settings → Service Accounts → Generate new private key
# Скопировать файл как /root/panel/serviceAccount.json

# Запустить через PM2
npm install -g pm2
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## Nginx конфиг для panel.br-v2.ru

```nginx
server {
    listen 80;
    server_name panel.br-v2.ru;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

После — certbot для SSL:
```bash
certbot --nginx -d panel.br-v2.ru
```
