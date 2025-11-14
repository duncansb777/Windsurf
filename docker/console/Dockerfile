# Console: Nginx serving the single-page demo and proxying /health-ui/ to demo-ui
FROM nginx:alpine

# Copy HTML as index
COPY /agentic-control-demo.html /usr/share/nginx/html/index.html

# Nginx config with proxy to demo-ui
COPY /docker/console/nginx.conf /etc/nginx/nginx.conf

EXPOSE 8000
CMD ["nginx", "-g", "daemon off;"]
