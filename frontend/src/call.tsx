// components/Dialpad.tsx
import React, { useState } from 'react';
import { Phone, X } from 'lucide-react';
import axios, { AxiosError } from 'axios';

interface CallResponse {
  success: boolean;
  message: string;
  call_sid?: string;
  call_id?: number;
  to?: string;
  error?: string;
}

interface DialpadProps {
  isOpen: boolean;
  number: string;
  onClose: () => void;
  onNumberChange: (value: string) => void;
}

const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_TENDER;

const Dialpad: React.FC<DialpadProps> = ({
  isOpen,
  number,
  onClose,
  onNumberChange,
}) => {
  const [calling, setCalling] = useState(false);
  const [message, setMessage] = useState('');

  const buttons = ['1','2','3','4','5','6','7','8','9','*','0','#'];

  const handlePress = (digit: string) => {
    onNumberChange(number + digit);
    setMessage('');
  };

  const handleBackspace = () => {
    onNumberChange(number.slice(0, -1));
  };

  const handleCall = async () => {
    if (!number) {
      setMessage('Please enter a number');
      return;
    }

    setCalling(true);
    setMessage('');

    try {
      const userId = localStorage.getItem('id') || localStorage.getItem('id');
      const username = localStorage.getItem('username') || 'web_dialpad';

      const response = await axios.post<CallResponse>(
        `${API_BASE_URL_A}/ap/calls/make/web/`,
        {
          to_number: number,
          purpose: 'web_dialpad',
          user_id: userId,
          username,
        },
        { headers: { 'Content-Type': 'application/json' } }
      );

      if (response.data.success) {
        setMessage('📞 Calling...');
        setTimeout(() => {
          onNumberChange('');
          setMessage('');
          onClose();       // close after connect
        }, 1200);
      } else {
        setMessage('❌ ' + response.data.message);
      }
    } catch (error) {
      const axiosError = error as AxiosError<CallResponse>;
      if (axiosError.response?.data?.message) {
        setMessage('❌ ' + axiosError.response.data.message);
      } else {
        setMessage('❌ Failed to make call');
      }
      console.error('Call error:', error);
    } finally {
      setCalling(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]">
      <div className="bg-white rounded-2xl shadow-2xl w-80 p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-bold text-center mb-6 text-gray-800">
          Make a Call
        </h2>

        <div className="bg-gray-100 rounded-lg p-4 mb-4 min-h-[60px] flex items-center justify-center">
          <input
            type="tel"
            value={number}
            onChange={e => onNumberChange(e.target.value)}
            placeholder="Enter number"
            className="text-2xl font-mono text-center w-full bg-transparent outline-none"
            maxLength={15}
          />
        </div>

        {message && (
          <div className={`text-center mb-2 text-sm ${
            message.includes('❌') ? 'text-red-500' : 'text-green-600'
          }`}>
            {message}
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 mb-4">
          {buttons.map(btn => (
            <button
              key={btn}
              onClick={() => handlePress(btn)}
              className="bg-gray-100 hover:bg-gray-200 active:bg-gray-300 rounded-xl h-14 text-xl font-semibold transition-colors"
              disabled={calling}
            >
              {btn}
            </button>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleBackspace}
            className="flex-1 bg-gray-200 hover:bg-gray-300 rounded-xl py-3 font-semibold text-gray-700"
            disabled={calling || !number}
          >
            ⌫ Delete
          </button>
          <button
            onClick={handleCall}
            disabled={calling || !number}
            className="flex-1 bg-green-500 hover:bg-green-600 disabled:bg-gray-300 text-white rounded-xl py-3 font-semibold flex items-center justify-center gap-2"
          >
            <Phone className="w-5 h-5" />
            {calling ? 'Calling...' : 'Call'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dialpad;
