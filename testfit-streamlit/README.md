# TestFit Data Center Site Optimizer - Streamlit Web App

A sophisticated web application for optimizing data center building placement using AI-powered site analysis. Convert your desktop PyQt5 TestFit application into a secure, web-based tool.

## 🚀 Features

- **AI-Powered Optimization**: Advanced algorithms find optimal building placement
- **Constraint-Aware Planning**: Respects setbacks, environmental features, and regulations  
- **Multiple Building Types**: Support for various data center configurations
- **Smart Substation Placement**: Automatically calculates and places required substations
- **Interactive Visualization**: 2D plots and interactive maps with Folium
- **Secure Access**: Password protection to keep your app private
- **Export Capabilities**: KML, JSON, and CSV export options

## 📋 Prerequisites

- Python 3.8 or higher
- pip package manager

## 🛠️ Installation & Setup

### 1. Create Project Directory

```bash
mkdir testfit-streamlit
cd testfit-streamlit
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv testfit-env

# Activate environment
# On Windows:
testfit-env\Scripts\activate
# On macOS/Linux:
source testfit-env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Directory Structure

```
testfit-streamlit/
├── app.py                    # Main Streamlit app
├── requirements.txt          # Dependencies
├── .streamlit/
│   ├── config.toml          # Streamlit configuration
│   └── secrets.toml         # Password and secrets
├── testfit/                 # Core modules
│   ├── __init__.py
│   ├── models.py           # Building specs, data classes
│   ├── parser.py           # KML parsing logic
│   ├── optimizer.py        # Optimization algorithms
│   └── visualizer.py       # Plotting functions
└── README.md
```

### 5. Configure Security

Edit `.streamlit/secrets.toml` and change the default password:

```toml
app_password = "your_secure_password_here"
```

**⚠️ Important**: Keep this file secure and never commit it to public repositories!

## 🏃‍♂️ Running the Application

### Local Development

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Network Access

To allow access from other computers on your network:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## 🔐 Security Options

### 1. Password Protection (Built-in)
- Default password: `testfit2024`
- Change in `.streamlit/secrets.toml`
- Simple but effective for small teams

### 2. VPN/Network Isolation
- Run on internal network only
- Use VPN for remote access
- Most secure option

### 3. Cloud Deployment with Authentication
- Deploy to Streamlit Cloud (free)
- Use Google Cloud Run with IAM
- Corporate authentication integration

## 🌐 Deployment Options

### Option A: Streamlit Cloud (Recommended for Simplicity)

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial TestFit Streamlit app"
   git remote add origin your-repo-url
   git push -u origin main
   ```

2. **Deploy to Streamlit Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repo
   - Set secrets in the Streamlit Cloud dashboard
   - Deploy automatically

3. **Set Secrets**:
   - In Streamlit Cloud dashboard, go to App Settings > Secrets
   - Add: `app_password = "your_secure_password"`

### Option B: Google Cloud Run

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY . .
   
   EXPOSE 8080
   CMD streamlit run app.py --server.port 8080 --server.address 0.0.0.0
   ```

2. **Deploy**:
   ```bash
   gcloud run deploy testfit-optimizer \
       --source . \
       --platform managed \
       --region us-central1 \
       --allow-unauthenticated \
       --memory 2Gi
   ```

### Option C: Self-Hosted with Docker

1. **Build Container**:
   ```bash
   docker build -t testfit-streamlit .
   ```

2. **Run Container**:
   ```bash
   docker run -p 8501:8501 testfit-streamlit
   ```

## 📖 Usage Guide

### 1. Upload KML File
- Supported formats: `.kml`, `.kmz`
- File should contain site boundaries and constraint features
- Max file size: 200MB

### 2. Configure Settings
- **Max Power**: Set power capacity limits (MW)
- **Max Height**: Set building height restrictions (ft)
- **Yard Options**: Configure generator and cooling yard placement
- **Existing Infrastructure**: Account for existing substations

### 3. Select Constraints
- Choose which features should be treated as no-build zones
- Features are automatically classified by type
- Setback distances are applied automatically

### 4. Manage Building Types
- Use default building specifications or create custom types
- Enable/disable building types for optimization
- Edit specifications in the Building Types tab

### 5. Run Optimization
- Click "Optimize Layout" to start the AI optimization process
- Multiple trials test different configurations
- Results show optimal building and substation placement

### 6. View Results
- **Site Layout**: 2D visualization of optimized layout
- **Interactive Map**: Folium-based interactive map with detailed popups
- **Building Details**: Detailed table of all placed buildings
- **Export Options**: Download results in KML, JSON, or CSV format

## 🎯 Key Features Explained

### Building Type Management
- **Pre-configured Types**: Small, Medium, Large, and Hyperscale data centers
- **Custom Types**: Create your own building specifications
- **Yard Configuration**: Flexible generator and cooling yard placement
- **Power Calculations**: Automatic IT power and utility power calculations

### Constraint Processing
- **Automatic Classification**: Features auto-classified by name/description
- **Smart Setbacks**: Different setback distances for different feature types
- **Power Feature Recognition**: Power lines guide substation placement
- **Environmental Features**: Wetlands, floodplains, existing buildings

### Optimization Algorithm
- **Multi-Trial Approach**: Tests multiple configurations to find optimal layout
- **Constraint Avoidance**: Respects all selected constraints and setbacks
- **Power Balancing**: Automatically calculates required substation capacity
- **Collision Detection**: Ensures buildings don't overlap or violate constraints

### Visualization
- **2D Site Plot**: Matplotlib-based technical drawings
- **Interactive Maps**: Folium maps with detailed building information
- **Color Coding**: Different colors for building types and constraint types
- **Detailed Labels**: Power, area, and configuration information on each building

## 🔧 Customization

### Adding New Building Types
```python
custom_spec = BuildingSpec(
    name="Custom AI Data Center",
    num_stories=1,
    num_data_halls=4,
    building_height=32,
    screen_height=28,
    width=250,
    length=120,
    gen_yard=50,
    cool_yard=30,
    gross_sqft=36000,
    data_hall_sqft=27000,
    low_it_mw=60.0,
    high_it_mw=80.0,
    low_watt_sqft=200,
    high_watt_sqft=250,
    utility_low_pue_mw=90.0,
    utility_high_pue_mw=120.0,
    color="purple",
    enabled=True
)
```

### Modifying Constraint Setbacks
```python
# In testfit/parser.py, modify layer_base_setbacks
self.layer_base_setbacks = {
    'roads': 25,        # Increased from 20ft
    'wetlands': 150,    # Increased from 100ft
    'power_lines': 15,  # Increased from 10ft
    # ... other setbacks
}
```

### Custom Visualization
```python
# In testfit/visualizer.py, modify create_site_visualization
# Add custom colors, labels, or plot elements
```

## 🐛 Troubleshooting

### Common Issues

1. **"No buildable area after applying constraints"**
   - Check if constraints cover entire site
   - Reduce setback distances if needed
   - Verify KML file contains valid site boundary

2. **"No enabled building specifications"**
   - Enable at least one building type in Building Management tab
   - Check height constraints aren't too restrictive

3. **Password not working**
   - Check `.streamlit/secrets.toml` file exists
   - Verify password spelling and case sensitivity
   - Restart Streamlit app after changing password

4. **Large file upload issues**
   - Check file size < 200MB
   - Verify KML/KMZ file format
   - Try simplifying complex geometries

5. **Slow optimization**
   - Reduce number of trials (default: 30)
   - Simplify site constraints
   - Use fewer building types

### Debug Mode

```bash
streamlit run app.py --logger.level debug
```

## 📊 Performance Guidelines

### Optimization Performance
- **Small sites** (< 50 acres): ~30 seconds
- **Medium sites** (50-200 acres): ~2-3 minutes  
- **Large sites** (> 200 acres): ~5-10 minutes
- **Complex sites** (many constraints): +50% time

### Memory Usage
- **Typical site**: 50-100MB RAM
- **Large sites**: 200-500MB RAM
- **Complex geometries**: Up to 1GB RAM

## 🔄 Migration from PyQt5 Version

### Key Differences
1. **Web Interface**: Browser-based instead of desktop
2. **Session State**: Data persists during browser session
3. **File Upload**: Drag-and-drop file upload interface
4. **Visualization**: Enhanced with interactive maps
5. **Export**: Direct download buttons instead of file dialogs

### Data Compatibility
- KML/KMZ files work unchanged
- Building specifications are compatible
- Optimization results are identical

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review Streamlit documentation

## 🎉 What's Next?

### Potential Enhancements
- **Database Integration**: Store optimization results
- **User Accounts**: Multi-user support with saved projects
- **Advanced Analytics**: Cost analysis and ROI calculations
- **3D Visualization**: Three.js integration for 3D site views
- **API Integration**: Connect to external data sources
- **Collaboration Features**: Team sharing and commenting

### Advanced Deployment
- **Load Balancing**: Handle multiple users
- **Auto-scaling**: Dynamic resource allocation
- **Monitoring**: Application performance monitoring
- **Backup**: Automated data backup solutions