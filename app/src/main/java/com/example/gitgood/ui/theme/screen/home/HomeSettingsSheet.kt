package com.example.gitgood.ui.theme.screen.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.gitgood.ui.theme.GitGoodTheme

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun HomeSettingsSheet(
    darkTheme: Boolean,
    onDarkThemeChange: (Boolean) -> Unit,
    onSignOut: () -> Unit,
    onDismiss: () -> Unit,
    isSigningOut: Boolean
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MaterialTheme.colorScheme.surface
    ) {
        Column(Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
            Text("Settings", Modifier.padding(horizontal = 24.dp, vertical = 12.dp),
                style = MaterialTheme.typography.headlineSmall)
            ListItem(
                modifier = Modifier.toggleable(
                    value = darkTheme, enabled = !isSigningOut,
                    role = Role.Switch, onValueChange = onDarkThemeChange
                ),
                leadingContent = { Icon(if (darkTheme) Icons.Outlined.DarkMode else Icons.Outlined.LightMode, contentDescription = null) },
                headlineContent = { Text("Dark mode") },
                supportingContent = { Text(if (darkTheme) "Dark theme is on" else "Light theme is on") },
                trailingContent = { Switch(checked = darkTheme, onCheckedChange = null, enabled = !isSigningOut) },
                colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surface)
            )
            ListItem(
                modifier = Modifier.clickable(enabled = !isSigningOut, role = Role.Button, onClick = onSignOut),
                leadingContent = { Icon(Icons.AutoMirrored.Outlined.Logout, contentDescription = null) },
                headlineContent = { Text(if (isSigningOut) "Signing out…" else "Sign out") },
                supportingContent = { Text("Return to the welcome screen") },
                colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surface)
            )
        }
    }
}

@Preview(name = "Settings · dark", showBackground = true)
@Composable
private fun SettingsDarkPreview() {
    GitGoodTheme(darkTheme = true) { HomeSettingsSheet(true, {}, {}, {}, false) }
}
