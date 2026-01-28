// src/Login.tsx
import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './context/auth';
import { AlertCircle } from 'lucide-react';

const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const navigate = useNavigate();
  const { checkUserStatus } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      console.log('🔐 Attempting login...');
      const res = await axios.post(`${API_BASE_URL_A}/ap/login/`, { 
        username, 
        password 
      });
      
      console.log('✅ Login response:', res.data);
      const token = res.data.token;
      
      // Save token
      localStorage.setItem('auth_token', token);
      
      console.log('✅ Token saved:', token);
      
      // ✅ Verify token was saved
      const savedToken = localStorage.getItem('auth_token');
      console.log('✅ Verified saved token:', savedToken);
      
      // ✅ Verify token with backend and get user role
      console.log('🔄 Verifying user role...');
      await checkUserStatus();
      
      console.log('✅ Login successful - redirecting to dashboard');
      navigate('/dashboard');
      
    } catch (error: any) {
      console.error('❌ Login failed:', error);
      console.error('❌ Error response:', error.response?.data);
      
      // Clear token if exists
      localStorage.removeItem('auth_token');
      
      // Set user-friendly error message
      if (error.response?.status === 400) {
        setError('Invalid credentials. Please check your username and password.');
      } else if (error.response?.status === 401) {
        setError('Authentication failed. Please try again.');
      } else if (error.response?.status === 500) {
        setError('Server error. Please try again later.');
      } else if (error.message === 'Network Error') {
        setError('Cannot connect to server. Please check your connection.');
      } else {
        setError(error.response?.data?.detail || error.response?.data?.error || 'Login failed. Please try again.');
      }
      
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <form onSubmit={handleLogin} className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-sm">
        <h2 className="text-3xl font-bold mb-6 text-center text-blue-800">Agent Login</h2>
        
        {/* ✅ Error Alert */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}
        
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">Username</label>
          <input 
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" 
            placeholder="Enter username" 
            value={username}
            onChange={e => {
              setUsername(e.target.value);
              setError(''); // Clear error on input
            }}
            disabled={loading}
            required
          />
        </div>
        
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
          <input 
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" 
            type="password" 
            placeholder="Enter password"
            value={password}
            onChange={e => {
              setPassword(e.target.value);
              setError(''); // Clear error on input
            }}
            disabled={loading}
            required
          />
        </div>
        
        <button 
          type="submit"
          disabled={loading}
          className={`w-full text-white p-3 rounded-lg font-bold transition shadow-lg ${
            loading 
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-blue-600 hover:bg-blue-700 hover:shadow-xl'
          }`}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              Signing in...
            </span>
          ) : (
            'Sign In'
          )}
        </button>

        {/* ✅ Optional: Show what's happening during login */}
        {loading && (
          <p className="text-xs text-center text-gray-500 mt-3">
            Verifying credentials and permissions...
          </p>
        )}
      </form>
    </div>
  );
};

export default Login;