import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import AlertItem from '../components/AlertItem';
import { fetchAlerts, resolveAlert } from '../api/endpoints';
import type { Alert as AlertType } from '../types';

export default function AlertsScreen() {
  const [alerts, setAlerts] = useState<AlertType[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchAlerts();
      setAlerts(data);
    } catch (err) {
      console.warn('Failed to load alerts:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      loadData();
    }, [loadData])
  );

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleResolve = async (alertId: number) => {
    setResolvingId(alertId);
    try {
      await resolveAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_resolved: true, resolved_at: new Date().toISOString() } : a))
      );
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to resolve alert';
      Alert.alert('Error', msg);
    } finally {
      setResolvingId(null);
    }
  };

  const unresolvedAlerts = alerts.filter((a) => !a.is_resolved);
  const resolvedAlerts = alerts.filter((a) => a.is_resolved);

  if (loading && alerts.length === 0) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1a73e8" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.title}>Alerts</Text>
      <Text style={styles.subtitle}>
        {unresolvedAlerts.length} unresolved, {resolvedAlerts.length} resolved
      </Text>

      {alerts.length === 0 && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No alerts at this time.</Text>
        </View>
      )}

      {unresolvedAlerts.map((alert) => (
        <AlertItem
          key={alert.id}
          id={alert.id}
          alertType={alert.alert_type}
          severity={alert.severity}
          message={alert.message}
          isResolved={alert.is_resolved}
          createdAt={alert.created_at}
          onResolve={resolvingId === alert.id ? undefined : handleResolve}
        />
      ))}

      {resolvedAlerts.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Resolved</Text>
          {resolvedAlerts.map((alert) => (
            <AlertItem
              key={alert.id}
              id={alert.id}
              alertType={alert.alert_type}
              severity={alert.severity}
              message={alert.message}
              isResolved={alert.is_resolved}
              createdAt={alert.created_at}
            />
          ))}
        </>
      )}
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
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f7fa',
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#222',
  },
  subtitle: {
    fontSize: 14,
    color: '#888',
    marginBottom: 16,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#888',
    marginTop: 20,
    marginBottom: 10,
  },
  emptyState: {
    marginTop: 60,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 15,
    color: '#999',
  },
});
