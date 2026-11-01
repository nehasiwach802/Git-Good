
package com.example.gitgood.ui.screen.auth.register

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.gitgood.R
import com.example.gitgood.ui.theme.*

@Composable
fun RegisterScreenLayout(
    uiState: RegisterUiState,
    onEmailInput: (String) -> Unit,
    onPasswordInput: (String) -> Unit,
    onConfirmPasswordInput: (String) -> Unit,
    onPasswordVisibilityToggle: () -> Unit,
    onConfirmPasswordVisibilityToggle: () -> Unit,
    onSignUpClick: () -> Unit,
    onGoogleClick: () -> Unit,
    onLoginClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BackgroundColor)
            .padding(horizontal = 28.dp)
            .padding(top = 38.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {

        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(modifier =Modifier.height(50.dp))

            Text(
                text = "Your next chapter.",
                fontSize = 35.sp,
                lineHeight = 42.sp,
                fontWeight = FontWeight.Medium,
                letterSpacing = (-1.3).sp,
                color = PrimaryTextColor
            )

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = "Create an account. Make it yours.",
                fontSize = 16.sp,
                color = SecondaryTextColor
            )

            Spacer(modifier = Modifier.height(36.dp))

            RegisterInputField(
                label = "Email address",
                value = uiState.email,
                onValueChange = onEmailInput,
                placeholder = "you@example.com",
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next
            )

            Spacer(modifier = Modifier.height(20.dp))

            RegisterInputField(
                label = "Password",
                value = uiState.password,
                onValueChange = onPasswordInput,
                placeholder = "Create a password",
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Next,
                isPassword = true,
                passwordVisible = uiState.isPasswordVisible,
                onPasswordVisibilityToggle =
                    onPasswordVisibilityToggle
            )

            Spacer(modifier = Modifier.height(20.dp))

            RegisterInputField(
                label = "Confirm password",
                value = uiState.confirmPassword,
                onValueChange = onConfirmPasswordInput,
                placeholder = "Re-enter your password",
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done,
                isPassword = true,
                passwordVisible = uiState.isConfirmPasswordVisible,
                onPasswordVisibilityToggle =
                    onConfirmPasswordVisibilityToggle
            )

            Spacer(modifier = Modifier.height(26.dp))

            Button(
                onClick = onSignUpClick,
                enabled = !uiState.isLoading,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = PrimaryGreen
                )
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(22.dp),
                        color = OnPrimaryColor,
                        strokeWidth = 2.dp
                    )
                } else {
                    Text(
                        text = "Create account",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = OnPrimaryColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            OutlinedButton(
                onClick = onGoogleClick,
                enabled = !uiState.isLoading,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp),
                shape = RoundedCornerShape(14.dp),
                border = androidx.compose.foundation.BorderStroke(
                    1.dp,
                    BorderColor
                ),
                colors = ButtonDefaults.outlinedButtonColors(
                    containerColor = BackgroundColor
                )
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    Image(
                        painter = painterResource(R.drawable.google_logo),
                        contentDescription = "Google logo",
                        modifier = Modifier.size(20.dp)
                    )

                    Spacer(modifier = Modifier.width(12.dp))

                    Text(
                        text = "Continue with Google",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Medium,
                        color = PrimaryTextColor
                    )
                }
            }
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 16.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Already have an account? ",
                fontSize = 14.sp,
                color = SecondaryTextColor
            )

            Text(
                text = "Log in",
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = PrimaryGreen,
                modifier = Modifier.clickable {
                    onLoginClick()
                }
            )
        }
    }
}

@Composable
private fun RegisterInputField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    keyboardType: KeyboardType,
    imeAction: ImeAction,
    isPassword: Boolean = false,
    passwordVisible: Boolean = false,
    onPasswordVisibilityToggle: () -> Unit = {}
) {
    Column(
        modifier = Modifier.fillMaxWidth()
    ) {

        Text(
            text = label,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            color = PrimaryTextColor
        )

        Spacer(modifier = Modifier.height(9.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(58.dp)
                .border(
                    width = 1.dp,
                    color = BorderColor,
                    shape = RoundedCornerShape(14.dp)
                )
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {

            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                singleLine = true,
                textStyle = TextStyle(
                    fontSize = 14.sp,
                    color = PrimaryTextColor
                ),
                keyboardOptions = KeyboardOptions(
                    keyboardType = keyboardType,
                    imeAction = imeAction
                ),
                visualTransformation = if (
                    isPassword && !passwordVisible
                ) {
                    PasswordVisualTransformation()
                } else {
                    VisualTransformation.None
                },
                decorationBox = { innerTextField ->
                    Box {
                        if (value.isEmpty()) {
                            Text(
                                text = placeholder,
                                fontSize = 14.sp,
                                color = SecondaryTextColor
                            )
                        }

                        innerTextField()
                    }
                }
            )

            if (isPassword) {
                Text(
                    text = if (passwordVisible) "◉" else "⊘",
                    fontSize = 20.sp,
                    color = SecondaryTextColor,
                    modifier = Modifier
                        .clickable {
                            onPasswordVisibilityToggle()
                        }
                        .padding(start = 12.dp)
                )
            }
        }
    }
}


@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun RegisterScreenLayoutPreview() {
    RegisterScreenLayout(
        uiState = RegisterUiState(),
        onEmailInput = {},
        onPasswordInput = {},
        onConfirmPasswordInput = {},
        onPasswordVisibilityToggle = {},
        onConfirmPasswordVisibilityToggle = {},
        onSignUpClick = {},
        onGoogleClick = {},
        onLoginClick = {}
    )
}

