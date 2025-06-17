// tailwind.config.js
module.exports = {
  content: [
    "./templates/**/*.html",
    "./myapp/templates/**/*.html",  // Add other apps if needed
  ],
  // Enable PurgeCSS only in production
  purge: {
    enabled: process.env.NODE_ENV === 'production',
    content: [
      "./templates/**/*.html",
      "./myapp/templates/**/*.html",
    ],
  },
}