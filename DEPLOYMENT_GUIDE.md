# IoT Anomaly Detection Dashboard - AWS Amplify Deployment Guide

## Overview
This guide will help you deploy your React IoT Dashboard to AWS Amplify using the provided CloudFormation template and GitHub repository.

## Prerequisites
- AWS CLI configured with appropriate permissions
- GitHub repository: https://github.com/aditiprashant07/React-Project
- GitHub OAuth token: `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`

## Project Structure
The project has been optimized for AWS Amplify deployment with the following key files:

### Configuration Files
- `package.json` - Updated with homepage configuration for Amplify
- `amplify.yml` - Build specification for Amplify
- `amplify-application.yaml` - CloudFormation template for infrastructure
- `.env.example` - Environment variables template

### Key Features Added
- ✅ Environment variable support for API endpoints
- ✅ Proper build configuration for Amplify
- ✅ Error handling and timeout for production
- ✅ Optimized HTML meta tags
- ✅ Git-based deployment support

## Deployment Steps

### 1. Prepare Your GitHub Repository
Ensure your repository at `https://github.com/aditiprashant07/React-Project` contains:
- All the React application files
- `package.json` with build script
- `amplify.yml` build specification
- `.env.example` file

### 2. Deploy CloudFormation Stack
Use the provided CloudFormation template to create your Amplify application:

```bash
aws cloudformation create-stack \
  --stack-name iot-dashboard-amplify \
  --template-body file://amplify-application.yaml \
  --parameters ParameterKey=AppName,ParameterValue=Iot-Dashboard \
               ParameterKey=BranchName,ParameterValue=main \
               ParameterKey=Repository,ParameterValue=https://github.com/aditiprashant07/React-Project \
               ParameterKey=OAuthToken,ParameterValue=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 \
  --capabilities CAPABILITY_IAM
```

### 3. Monitor Deployment
Check the CloudFormation stack status:
```bash
aws cloudformation describe-stacks --stack-name iot-dashboard-amplify
```

### 4. Access Your Application
Once deployed, you can access your application at:
- Default domain: Available in CloudFormation outputs
- Custom domain: Configure in Amplify console if needed

## Environment Variables
The application uses the following environment variables:

- `REACT_APP_API_ENDPOINT`: API endpoint for anomaly detection
- `REACT_APP_ENVIRONMENT`: Environment identifier (production)
- `REACT_APP_BUILD_TYPE`: Build type identifier (amplify)

## Build Process
The Amplify build process follows these steps:
1. Install dependencies with `npm ci`
2. Build the React application with `npm run build`
3. Deploy the `build` folder contents

## Troubleshooting

### Common Issues
1. **Repository Access Denied**
   - Verify GitHub token has correct permissions
   - Check repository URL is correct

2. **Build Failures**
   - Check `package.json` has `build` script
   - Verify all dependencies are listed
   - Check `amplify.yml` syntax

3. **API Connection Issues**
   - Verify API endpoint is accessible
   - Check CORS configuration on API Gateway
   - Verify environment variables are set correctly

### Build Logs
Check Amplify console for detailed build logs if deployment fails.

## Local Development
To run locally:
```bash
npm install
npm start
```

To test production build:
```bash
npm run build
npm install -g serve
serve -s build
```

## Support
If you encounter issues:
1. Check AWS Amplify console for build logs
2. Verify CloudFormation stack events
3. Ensure GitHub repository is accessible
4. Check API endpoint connectivity

## Next Steps
After successful deployment:
1. Configure custom domain (optional)
2. Set up monitoring and alerts
3. Configure CI/CD for automatic deployments
4. Add additional environment variables as needed
