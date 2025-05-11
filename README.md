# SocialScope

**SocialScope** is a social media research tool designed to provide simplified insights from TikTok and Instagram profiles using third-party APIs. It was developed as part of a final-year Computer Science project.

## 🎯 Project Objective

To create a user-friendly platform that helps influencers and general users gain insights into their social media performance, even without access to official business-level APIs.

## 🔧 Technologies Used

- **Flask** – Backend framework
- **Firebase** – User authentication and database (Realtime Database)
- **Chart.js** – Frontend chart visualisation
- **Matplotlib** – Server-side graph generation (for PDF exports and hashtag trends)
- **WeasyPrint** – PDF report generation
- **TikTok Scraper API (RapidAPI)** – TikTok profile data
- **Instagram Premium API (RapidAPI)** – Instagram profile data
- **PyTrends** – Google Trends analysis for hashtags

## 💡 Key Features

- 🔍 Search TikTok and Instagram profiles
- 📊 Customisable charts showing profile insights
- 📁 Save/delete favourite profiles
- 📈 Hashtag trends with Google Trends integration
- 🧾 PDF report export for TikTok analytics
- 🔐 Email/password login system (Firebase Auth)
- ✅ Functional and usability testing with real influencers


## 🧪 Testing

- Manual testing with visual documentation  
- Usability testing with 20 participants (including 9 influencers)  
- Full results and quotes available in `/appendix/` and project report

## 📁 Project Structure

```
/static/             → CSS, images, Chart.js assets  
/templates/          → HTML frontend pages  
app.py               → Flask application logic  
firebase_credentials.json → Firebase service key  
```

## 🔗 Links

- 🔍 APIs used:  
  - [TikTok Scraper API](https://rapidapi.com/tikwm-tikwm-default/api/tiktok-scraper7)  
  - [Instagram Premium API](https://rapidapi.com/NikitusLLP/api/instagram-premium-api-2023)  
- 🔐 [Firebase](https://firebase.google.com/)  
- 📊 [Chart.js](https://www.chartjs.org/)  
- 🧾 [WeasyPrint](https://weasyprint.org/)

## 📄 Licence

This project was developed for academic use as part of a final-year university module. Not intended for commercial distribution.
