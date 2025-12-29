import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATE;
const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      console.log('🔐 Attempting login...');
      const res = await axios.post(`${API_BASE_URL_A}/ap/login/`, { 
        username, 
        password 
      });
      
      console.log('✅ Login response:', res.data);
      const token = res.data.token;
      
      // Save token with consistent key name
      localStorage.setItem('auth_token', token);  // Changed from 'token' to 'auth_token'
      console.log('✅ Token saved:', token);
      
      // Verify token was saved
      const savedToken = localStorage.getItem('auth_token');
      console.log('✅ Verified saved token:', savedToken);
      
      alert('Login successful! ✅');
      navigate('/dashboard');
      
    } catch (error: any) {
      console.error('❌ Login failed:', error);
      console.error('❌ Error response:', error.response?.data);
      
      if (error.response?.status === 400) {
        alert('Login Failed: Invalid credentials');
      } else if (error.response?.status === 500) {
        alert('Login Failed: Server error');
      } else {
        alert('Login Failed: ' + (error.response?.data?.detail || error.message));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <form onSubmit={handleLogin} className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-sm">
        <h2 className="text-3xl font-bold mb-6 text-center text-blue-800">Agent Login</h2>
        
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">Username</label>
          <input 
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
            placeholder="Enter username" 
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
          />
        </div>
        
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
          <input 
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
            type="password" 
            placeholder="Enter password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
        </div>
        
        <button 
          type="submit"
          disabled={loading}
          className={`w-full text-white p-3 rounded-lg font-bold transition shadow-lg ${
            loading 
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </div>
  );
};

export default Login;