import { Platform } from 'react-native';

// Expo Notifications registration helper
// In production, this would register with Expo's push notification service.
// For the initial scaffolding, we set up the notification handlers.

let notificationsInitialized = false;

export async function initNotifications(): Promise<void> {
  if (notificationsInitialized) return;

  try {
    // Dynamic import to avoid crashing on web
    const Notifications = await import('expo-notifications');
    const Device = await import('expo-device');

    // Configure notification handler
    Notifications.default.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });

    // Request permissions
    if (Device.default.isDevice) {
      const { status: existingStatus } = await Notifications.default.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.default.requestPermissionsAsync();
        finalStatus = status;
      }
      if (finalStatus !== 'granted') {
        console.warn('Push notification permission not granted');
        return;
      }
    }

    // Get push token (Expo push token for cloud messaging)
    if (Platform.OS !== 'web') {
      const tokenData = await Notifications.default.getExpoPushTokenAsync();
      console.log('Expo push token:', tokenData.data);
    }

    // Android notification channel
    if (Platform.OS === 'android') {
      Notifications.default.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.default.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#1a73e8',
      });
    }

    notificationsInitialized = true;
  } catch (err) {
    console.warn('Failed to initialize notifications:', err);
  }
}

export async function scheduleLocalNotification(title: string, body: string): Promise<void> {
  try {
    const Notifications = await import('expo-notifications');
    await Notifications.default.scheduleNotificationAsync({
      content: { title, body },
      trigger: null, // immediate
    });
  } catch (err) {
    console.warn('Failed to schedule notification:', err);
  }
}
