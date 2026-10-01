module.exports = {
  apps: [{
    name: 'br-panel',
    script: 'server.js',
    cwd: '/root/panel',
    env: {
      PORT: 3000,
      NODE_ENV: 'production',
    },
    restart_delay: 3000,
    max_restarts: 10,
  }]
};
