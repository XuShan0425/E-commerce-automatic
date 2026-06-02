import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { initClient } from '../api/client';

export default function SettingsScreen() {
  const { username, role, apiKey, logout, bindApiKey } = useAuth();
  const [newApiKey, setNewApiKey] = useState('');
  const [serverUrl, setServerUrl] = useState('http://localhost:8000');

  const handleBindApiKey = async () => {
    if (!newApiKey.trim()) {
      Alert.alert('Error', 'Please enter an API Key.');
      return;
    }
    try {
      await bindApiKey(newApiKey.trim());
      Alert.alert('Success', 'API Key bound successfully.');
      setNewApiKey('');
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to bind API Key.');
    }
  };

  const handleUpdateServerUrl = async () => {
    if (!serverUrl.trim()) {
      Alert.alert('Error', 'Please enter a server URL.');
      return;
    }
    try {
      await initClient(serverUrl.trim());
      Alert.alert('Success', 'Server URL updated. Re-login may be required.');
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to update server URL.');
    }
  };

  const handleLogout = () => {
    Alert.alert('Confirm Logout', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Logout', style: 'destructive', onPress: logout },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Settings</Text>

      {/* User Info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Username</Text>
          <Text style={styles.infoValue}>{username || '--'}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Role</Text>
          <Text style={styles.infoValue}>{role || '--'}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>API Key</Text>
          <Text style={styles.infoValue}>
            {apiKey ? `${apiKey.slice(0, 8)}...${apiKey.slice(-4)}` : 'Not bound'}
          </Text>
        </View>
      </View>

      {/* API Key Binding */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>API Key</Text>
        <Text style={styles.helpText}>
          Bind an API Key for public API access. Generate one from the web console.
        </Text>
        <TextInput
          style={styles.input}
          placeholder="Paste API Key"
          value={newApiKey}
          onChangeText={setNewApiKey}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TouchableOpacity style={styles.button} onPress={handleBindApiKey}>
          <Text style={styles.buttonText}>Bind API Key</Text>
        </TouchableOpacity>
      </View>

      {/* Server URL */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Server</Text>
        <TextInput
          style={styles.input}
          placeholder="http://localhost:8000"
          value={serverUrl}
          onChangeText={setServerUrl}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <TouchableOpacity style={styles.button} onPress={handleUpdateServerUrl}>
          <Text style={styles.buttonText}>Update Server URL</Text>
        </TouchableOpacity>
      </View>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f7fa',
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#222',
    marginBottom: 20,
  },
  section: {
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#333',
    marginBottom: 10,
  },
  helpText: {
    fontSize: 13,
    color: '#888',
    marginBottom: 10,
    lineHeight: 18,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f5f5f5',
  },
  infoLabel: {
    fontSize: 14,
    color: '#666',
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    backgroundColor: '#fafafa',
    marginBottom: 10,
  },
  button: {
    backgroundColor: '#1a73e8',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  logoutButton: {
    backgroundColor: '#fff',
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#d93025',
    marginTop: 8,
  },
  logoutText: {
    color: '#d93025',
    fontSize: 16,
    fontWeight: '600',
  },
});
