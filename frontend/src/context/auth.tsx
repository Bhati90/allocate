// src/context/auth.tsx
import React, { createContext, useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '@/types/config';

interface UserData {
  id: number;
  username: string;
  full_name: string;
  mobile_number: string;
  role: string;
  is_admin: boolean;
  is_verified: boolean;
}

interface AuthContextType {
  isAdmin: boolean;
  isLoading: boolean;
  userData: UserData | null;
  checkUserStatus: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null!);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [userData, setUserData] = useState<UserData | null>(null);

  // ✅ Function to verify token with Django
  const checkUserStatus = async () => {
    const token = localStorage.getItem('auth_token');
    
    if (!token) {
      console.log('❌ No token found');
      setIsAdmin(false);
      setUserData(null);
      setIsLoading(false);
      return;
    }

    try {
      console.log('🔄 Verifying token with backend...');
      const response = await axios.get(`${API_BASE_URL}/auth/me/`, {
        headers: { 
          'Authorization': `Token ${token}`,
        }
      });

      console.log('✅ Auth verified:', response.data);
      const id = response.data.id;
      localStorage.setItem('id', id);
      setIsAdmin(response.data.is_admin);
      setUserData(response.data);
      
    } catch (error: any) {
      console.error("❌ Auth check failed", error.response?.data || error.message);
      
      // ✅ Clear invalid token
      localStorage.removeItem('auth_token');
      setIsAdmin(false);
      setUserData(null);
      
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.clear();
    setIsAdmin(false);
    setUserData(null);
  };

  useEffect(() => {
    checkUserStatus();
  }, []);

  return (
    <AuthContext.Provider value={{ isAdmin, isLoading, userData, checkUserStatus, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};