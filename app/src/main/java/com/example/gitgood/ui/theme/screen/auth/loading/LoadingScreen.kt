package com.example.gitgood.ui.theme.screen.auth.loading

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.gitgood.R
import com.example.gitgood.ui.theme.BackgroundColor
import com.example.gitgood.ui.theme.BorderColor
import com.example.gitgood.ui.theme.LightGreen
import com.example.gitgood.ui.theme.PrimaryGreen
import com.example.gitgood.ui.theme.PrimaryTextColor
import com.example.gitgood.ui.theme.SecondaryTextColor


@Composable
fun CircuitlyWelcomeScreenLayout(
    onGetStartedClick: () -> Unit = {},
    onLoginClick: () -> Unit = {}
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundColor)
            .padding(horizontal = 28.dp)
            .padding(top = 16.dp, bottom = 22.dp),

        verticalArrangement = Arrangement.SpaceBetween,
        horizontalAlignment = Alignment.Start
    ) {

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Image(
                painter = painterResource(R.drawable.logo),
                contentDescription = "Circuitly Logo",
                modifier = Modifier.size(25.dp),
                contentScale = ContentScale.Fit
            )

            Text(
                text = "circuitly",
                fontSize = 23.sp,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = (-0.9).sp,
                color = PrimaryTextColor
            )
        }

        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(34.dp),
            horizontalAlignment = Alignment.Start
        ) {
            Box(
                modifier = Modifier
                    .size(112.dp)
                    .clip(RoundedCornerShape(32.dp))
                    .background(LightGreen),
                contentAlignment = Alignment.Center
            ) {
                Image(
                    painter = painterResource(R.drawable.logo),
                    contentDescription = "Circuitly Symbol",
                    modifier = Modifier.size(56.dp),
                    contentScale = ContentScale.Fit
                )
            }

            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
                horizontalAlignment = Alignment.Start
            ) {

                Text(
                    text = "STUDENT LIFE, SIMPLIFIED",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    letterSpacing = 1.5.sp,
                    color = PrimaryGreen
                )

                Column(
                    horizontalAlignment = Alignment.Start
                ) {
                    Text(
                        text = "Let’s get",
                        fontSize = 44.sp,
                        fontWeight = FontWeight.Medium,
                        letterSpacing = (-2).sp,
                        lineHeight = 49.sp,
                        color = PrimaryTextColor
                    )

                    Text(
                        text = "started.",
                        fontSize = 44.sp,
                        fontWeight = FontWeight.Medium,
                        letterSpacing = (-2).sp,
                        lineHeight = 49.sp,
                        color = PrimaryTextColor
                    )
                }

                Text(
                    text = "A new chapter starts here. Make yourself " +
                            "at home with Circuitly.",
                    fontSize = 16.sp,
                    lineHeight = 25.sp,
                    color = SecondaryTextColor
                )
            }
        }

        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {

            Button(
                onClick = onGetStartedClick,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = PrimaryGreen
                ),
                contentPadding = PaddingValues(horizontal = 20.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    Text(
                        text = "Get started",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )

                    Spacer(modifier = Modifier.width(12.dp))

                    Text(
                        text = "→",
                        fontSize = 20.sp,
                        color = Color.White
                    )
                }
            }

            OutlinedButton(
                onClick = onLoginClick,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp),
                shape = RoundedCornerShape(14.dp),
                border = BorderStroke(1.dp, BorderColor),
                colors = ButtonDefaults.outlinedButtonColors(
                    containerColor = BackgroundColor
                )
            ) {
                Text(
                    text = "I already have an account",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = PrimaryTextColor
                )
            }

            Text(
                text = "Made for students. Made for you.",
                fontSize = 12.sp,
                color = SecondaryTextColor
            )
        }
    }
}


@Preview(showBackground = true, showSystemUi = true)
@Composable
fun CircuitlyWelcomeScreenPreview() {
    CircuitlyWelcomeScreenLayout()
}