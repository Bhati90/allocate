// useCurrentUser.ts
import * as React from 'react';
import { API_BASE_URL } from '../types/config';

export interface CurrentUser {
  id: number;
  username: string;
  full_name: string;
  mobile_number: string;
  role: string;
  is_admin: boolean;
}

let _cached: CurrentUser | null = null;
let _promise: Promise<CurrentUser> | null = null;

function fetchCurrentUser(): Promise<CurrentUser> {
  if (_cached) return Promise.resolve(_cached);
  if (_promise) return _promise;

  const token = localStorage.getItem('auth_token');
  _promise = fetch(`${API_BASE_URL}/auth/me/`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    credentials: 'include',
  })
    .then(res => {
      if (!res.ok) throw new Error('Not authenticated');
      return res.json();
    })
    .then((data: CurrentUser) => {
      _cached = data;
      return data;
    })
    .catch(err => {
      _promise = null;
      throw err;
    });

  return _promise;
}

export function useCurrentUser() {
  const [user, setUser] = React.useState<CurrentUser | null>(_cached);
  const [loading, setLoading] = React.useState<boolean>(!_cached);

  React.useEffect(() => {
    if (_cached) {
      setUser(_cached);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetchCurrentUser()
      .then(u => {
        if (!cancelled) {
          setUser(u);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  return { user, loading };
}
