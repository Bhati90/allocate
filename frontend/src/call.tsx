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

const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

const Dialpad: React.FC = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [number, setNumber] = useState<string>('');
  const [calling, setCalling] = useState<boolean>(false);
  const [message, setMessage] = useState<string>('');

  const buttons: string[] = [
    '1', '2', '3',
    '4', '5', '6',
    '7', '8', '9',
    '*', '0', '#'
  ];

  const handlePress = (digit: string): void => {
    setNumber(prev => prev + digit);
    setMessage('');
  };

  const handleBackspace = (): void => {
    setNumber(prev => prev.slice(0, -1));
  };

  const handleCall = async (): Promise<void> => {
    if (!number) {
      setMessage('Please enter a number');
      return;
    }

    setCalling(true);
    setMessage('');

    try {
      // ✅ GET USER ID FROM localStorage (or your auth context)
      const userId = localStorage.getItem('id') || localStorage.getItem('id');
      const username = localStorage.getItem('username') || 'web_dialpad';

      const response = await axios.post<CallResponse>(
        `${API_BASE_URL_A}/ap/calls/make/web/`,
        {
          to_number: number,
          purpose: 'web_dialpad',
          user_id: userId,        // ✅ SEND USER ID
          username: username      // ✅ SEND USERNAME (optional)
        },
        {
          headers: {
            'Content-Type': 'application/json',
          }
        }
      );

      if (response.data.success) {
        setMessage('📞 Calling...');
        setTimeout(() => {
          setNumber('');
          setMessage('');
        }, 2000);
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

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-green-500 hover:bg-green-600 text-white rounded-full p-4 shadow-lg transition-all hover:scale-110 z-50"
        title="Open Dialpad"
      >
        <Phone className="w-6 h-6" />
      </button>

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-80 p-6 relative">
            {/* Close Button */}
            <button
              onClick={() => setIsOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h2 className="text-xl font-bold text-center mb-6 text-gray-800">
              Make a Call
            </h2>

            {/* Display */}
            <div className="bg-gray-100 rounded-lg p-4 mb-4 min-h-[60px] flex items-center justify-center">
              <input
                type="tel"
                value={number}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNumber(e.target.value)}
                placeholder="Enter number"
                className="text-2xl font-mono text-center w-full bg-transparent outline-none"
                maxLength={15}
              />
            </div>

            {/* Message */}
            {message && (
              <div className={`text-center mb-2 text-sm ${
                message.includes('❌') ? 'text-red-500' : 'text-green-600'
              }`}>
                {message}
              </div>
            )}

            {/* Dialpad Grid */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              {buttons.map((btn) => (
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

            {/* Action Buttons */}
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
      )}
    </>
  );
};

export default Dialpad;