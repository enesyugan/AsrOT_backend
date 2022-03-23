from django.shortcuts import render
from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response

import datetime

from .permissions import CanMakeAssignments
from . import selectors
from . import services
# Create your views here.



class LogInApi(APIView):

    class LogInSerializer(serializers.Serializer):
        email = serializers.EmailField()
        password = password = serializers.CharField(
        	write_only=True,
        	required=True,        
        	style={'input_type': 'password', 'placeholder': 'Password'}
	   	)

        def validate_(self, validated_data):
            email = validated_data['email']
            user = authenticate(email=email, password= validated_data['password'])
            if not user:
                raise serializers.ValidationError("Could not login with provided credentials")
            return user
    

    def post(self, request):
        serializer = self.LogInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validate_(serializer.validated_data)
        try:
            token = Token.objects.get(user_id=user.id)
        except Token.DoesNotExist:
            token = Token.objects.create(user=user)

        return Response({"token": token.key}, status=status.HTTP_200_OK)



class LogOutApi(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_200_OK)



class UserInfoApi(APIView):
    permission_classes = [IsAuthenticated]


    class OutputSerializer(serializers.Serializer):
        email = serializers.EmailField()
        restricted = serializers.BooleanField(source='restricted_account')
        canMakeAssignments = serializers.BooleanField(source='can_make_assignments')
        langs = serializers.PrimaryKeyRelatedField(read_only=True, many=True, source='languages')


    def post(self, request):
        out_ser = self.OutputSerializer(instance=request.user)
        return Response(out_ser.data, status=status.HTTP_200_OK)


'''
class AuthTokenValidate(APIView):

    def post(self, request: "Request", *args, **kwargs) -> Response:
        token = request.body.decode("utf-8") # TODO Set mime in mediator so we can use data
        #print(token) # TODO remove
        #print(request)
        try: 
            user = Token.objects.get(key=token).user
            user.auth_token.delete()
            return Response("ok", 200)
        except Exception as e:
            print(e)        
        
        return Response("denied", 403)

class ListUsers(APIView):
    permission_classes = [IsAuthenticated]

    class OutputSerializer(serializers.Serializer):
        username = serializers.CharField(max_length=500)
        expire_date = serializers.DateField()
        is_superuser = serializers.BooleanField()       

    def get(self, request):
        if not request.user.is_superuser:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        users = selectors.user_list()
        out_serializer = self.OutputSerializer(users, many=True)         

        return Response({"users": out_serializer.data}, status=status.HTTP_200_OK)
'''


class RegisterUserApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(required=True)
        password = serializers.CharField(
            write_only=True,
            required=True,
            style={'input_type': 'password', 'placeholder': 'Password'}
        )
        langs = serializers.PrimaryKeyRelatedField(
            queryset=selectors.get_language_list(),
            many=True,
        )


    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.user_register(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            langs=serializer.validated_data['langs'],
        )
        return Response({"user": serializer.data}, status=status.HTTP_201_CREATED)


'''
class DeleteUser(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        username = serializers.CharField(max_length=500, required=True)

    def post(self, request):
        if not request.user.is_superuser:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
         
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.user_delete(serializer=serializer)

        return Response({"user": serializer.data}, status=status.HTTP_200_OK)

class EditUser(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        username = serializers.CharField(max_length=500, required=True)
        expire_date = serializers.DateField(required=False)       
        password = serializers.CharField(
                write_only=True,
                required=False,
                style={'input_type': 'password', 'placeholder': 'Password'}
                )

    def post(self, request):
        if not request.user.is_superuser:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
         
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get('password', None) != None:
            serializer.validated_data['password'] = make_password(serializer.validated_data.get('password'))
        services.user_edit(serializer=serializer)
        
        return Response(status=status.HTTP_200_OK)

'''
    

class UserListView(APIView):
    permission_classes = [IsAuthenticated, CanMakeAssignments]

    class FilterSerializer(serializers.Serializer):
        query = serializers.CharField(required=False, default='')
        langs = serializers.CharField(required=False, default=None)

        def validate_langs(self, value):
            langs = value.split(',')
            return selectors.get_language_list(filters={'short__in':langs})


    class OutputSerializer(serializers.Serializer):
        email = serializers.EmailField()


    def get(self, request, *args, **kwargs):
        filter_ser = self.FilterSerializer(data=request.query_params)
        filter_ser.is_valid(raise_exception=True)
        filters={
            'email__startswith': filter_ser.validated_data['query']
        }
        if filter_ser.validated_data['langs']:
            filters['languages__in'] = filter_ser.validated_data['langs']
        queryset = selectors.get_user_list(filters=filters).distinct()
        serializer = self.OutputSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class LanguageListView(APIView):

    class FilterSerializer(serializers.Serializer):
        onlyASR = serializers.BooleanField(required=False, default=False)
    
    class OutputSerializer(serializers.Serializer):
        short = serializers.SlugField()
        english_name = serializers.CharField()
        native_name = serializers.CharField()


    def get(self, request, *args, **kwargs):
        filter_ser = self.FilterSerializer(data=request.query_params)
        filter_ser.is_valid(raise_exception=True)
        if filter_ser.validated_data['onlyASR']:
            queryset = selectors.get_language_list(asr=True)
        else:
            queryset = selectors.get_language_list()
        serializer = self.OutputSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)