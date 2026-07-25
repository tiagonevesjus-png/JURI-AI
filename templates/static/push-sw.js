self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || 'JURI-AI', {
    body: data.body || 'Novo alerta recebido.',
    icon: '/static/favicon.ico',
    data: { url: data.url || '/notificacoes/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
