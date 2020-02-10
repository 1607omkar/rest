#!/bin/bash
  
lambda='testenv'
echo "Enter Lambda function in question"
read lambda
echo "Enter the region"
read region
isNAT=false
vpcid=$(aws lambda get-function-configuration --function-name $lambda --region $region --query "VpcConfig.VpcId" --output text)
printf "\n----------------------------------------------------"
printf "\nLambda function is in $vpcid"
if [ -z "$vpcid" ]
        then
        printf "\n ** The lambda function $lambda is not in VPC \n"
else
        for routetable in `aws ec2 describe-route-tables --region $region --query "RouteTables[?VpcId=='$vpcid'].RouteTableId" --output text`;
        do
                maintest=$(aws ec2 describe-route-tables --route-table-ids $routetable --region $region --query "RouteTables[*].Associations[0].Main" --output text)
                if [ $maintest = True ] ;
                then
                        fmain=$routetable
                fi
        done
        for subnets in `aws lambda get-function-configuration --function-name Internet --query "VpcConfig.SubnetIds" --region $region --output text`;
        do
                printf "\n The Subnets $subnets"
                route=$(aws ec2 describe-route-tables --region $region --query "RouteTables[*].Associations[?SubnetId=='$subnets'].RouteTableId" --output text)
                if [ -z "$route" ]
                then
                        gateway=$(aws ec2 describe-route-tables --route-table-ids $fmain --region $region --query "RouteTables[*].Routes[?DestinationCidrBlock=='0.0.0.0/0']" --output text | cut -f 2)
                        if [ ${gateway:0:3} == 'nat' ]
                                then
                                printf "\n\t - Default route of the subnet $subnets is pointing to NAT gateway $gateway"
                                gsubnet=$(aws ec2 describe-nat-gateways --nat-gateway-ids $gateway --region $region --query NatGateways[0].SubnetId --output text)
                                groute=$(aws ec2 describe-route-tables --region $region --query "RouteTables[*].Associations[?SubnetId=='$gsubnet'].RouteTableId" --output text)
                                ggateway=$(aws ec2 describe-route-tables --route-table-ids $groute --region $region --query "RouteTables[*].Routes[?DestinationCidrBlock=='0.0.0.0/0']" --output text | cut -f 2)
                                if [ ${ggateway:0:3} == 'igw' ]
                                        then
                                        printf "\n\t\t - Good Job, The NAT gateway is in public Subnet\n"
                                elif [ ${ggateway:0:3} == 'nat' ]
                                        then
                                        isNAT=false
                                        printf "\n [WARNING] You configured everything well upto NAT gateway but NAT gateway is also in private subnet which needs to be corrected!!!".
                                fi
                        elif [ ${gateway:0:3} == 'igw' ]
                                then
                                isNAT=false
                                printf "\n [WARNING]You need to have default gateway for Lambda as NAT gateway not IGW"
                        elif [ -z "$gateway" ]
                                then
                                isNAT=false
                                printf "[WARNING] Lambda function does not have default gateway!!!"
                        fi

                else
                        printf "\nThe route table value is $route\n"
                fi
        done
        printf "\n----------------------------------------------------"
        printf "\nNow lets check if execution role has the permissions."
        role=$(aws lambda get-function-configuration --function-name Internet --query Role --output text)
        rid=$(aws iam list-attached-role-policies --role-name ${role:31} --query AttachedPolicies[*].PolicyArn --output text)
        printf "Execution role has following policies:"
        for policy in $rid;
        do
                printf "\n-$policy"
                version=$(aws iam get-policy --policy-arn $policy --query Policy.DefaultVersionId --output text)
                pol=$(aws iam get-policy-version --policy-arn $policy --version-id $version --query PolicyVersion.Document.Statement[*].Action --output text)
                vpc_perm1="ec2:CreateNetworkInterface"
                vpc_perm2="ec2:DescribeNetworkInterfaces"
                vpc_perm3="ec2:DeleteNetworkInterface"
                if [[ "$pol" == *"$vpc_perm1"* ]] && [[ "$pol" == *"$vpc_perm2"* ]] && [[ "$pol" == *"$vpc_perm3"* ]];
                        then
                        printf "\n\tLambda function execution role has required permissions"
                        break
                else
                        printf "\n\t[WARNING] This policy does not have the required permissions. Lets check if the next policy has required permission"
                fi
        done
        printf "\n----------------------------------------------------"
fi
