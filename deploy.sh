#!/bin/bash
# deploy.sh - Deploys SpecTater to AWS Lambda with custom domain

set -e

APP_NAME="SpecTater"
DOMAIN_NAME="spectater.ai.oregonstate.edu"
AWS_REGION="us-west-2"
STACK_NAME="${APP_NAME}-stack"
BUCKET_NAME="${APP_NAME}-deploy-$(date +%s)"

# Create deployment bucket
echo "Creating deployment bucket: ${BUCKET_NAME}"
aws s3api create-bucket --bucket $BUCKET_NAME --region $AWS_REGION --create-bucket-configuration LocationConstraint=$AWS_REGION

# Generate SAM template
echo "Generating SAM template..."
cat << EOF > template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  ${APP_NAME}:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: app.app
      Runtime: python3.12
      Timeout: 30
      MemorySize: 2048
      Description: Policy document validation service
      Environment:
        Variables:
          AWS_REGION: $AWS_REGION
          MODEL_ID: $(grep MODEL_ID .env.default | cut -d'=' -f2)
      Events:
        Api:
          Type: Api
          Properties:
            Path: /{proxy+}
            Method: ANY
            RestApiId: !Ref ApiGateway

  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Domain:
        DomainName: $DOMAIN_NAME
        CertificateArn: !ImportValue ${APP_NAME}-CertificateArn
EOF

# Package and deploy
echo "Packaging application..."
sam package --template-file template.yaml --output-template-file packaged.yaml --s3-bucket $BUCKET_NAME

echo "Deploying application to AWS Lambda..."
sam deploy --template-file packaged.yaml --stack-name $STACK_NAME --capabilities CAPABILITY_IAM --region $AWS_REGION

# Cleanup
rm -f packaged.yaml template.yaml
aws s3 rb s3://$BUCKET_NAME --force

echo "Deployment complete!"
echo "Please configure DNS for $DOMAIN_NAME to point to the API Gateway endpoint."
echo "Use this CNAME record: $(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayDomainName`].OutputValue' --output text)"
