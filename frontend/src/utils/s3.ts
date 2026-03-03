// utils/s3Upload.ts
import axios from 'axios';

// ❌ WRONG - This uses VITE_API_BASE_URL_SUPPLY
// const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;

// ✅ CORRECT - Use the hardcoded demand URL for S3 uploads
const S3_UPLOAD_API_URL = 'https://demand.bharatintelligence.ai/chat';

// ✅ HARDCODED S3 UPLOAD TOKEN (for S3 upload API)
const S3_UPLOAD_TOKEN = 'e8fa8310c9af344ca22ec6bd23960d609b09c704';

/**
 * Upload a file to S3 using dual token authentication
 * @param file - The file to upload
 * @param s3ObjectName - The desired S3 object name
 * @param userAuthToken - User's authentication token (from localStorage)
 * @returns The S3 key if successful, null otherwise
 */
export const uploadFileToS3 = async (
  file: File,
  s3ObjectName: string,
  userAuthToken: string
): Promise<string | null> => {
  try {
    const formData = new FormData();
    
    // Add the file with field name 'image'
    formData.append('image', file, file.name);
    
    // Add the desired S3 object name
    formData.append('name_of_image', s3ObjectName);
    
    // ✅ ADD USER TOKEN as a form field
    formData.append('user_token', userAuthToken);

    console.log('📤 Uploading to S3...');
    console.log('  - File:', file.name);
    console.log('  - S3 Path:', s3ObjectName);
    console.log('  - API URL:', `${S3_UPLOAD_API_URL}/api/upload_image_to_s3/`);
    console.log('  - Using S3 Token:', S3_UPLOAD_TOKEN.substring(0, 10) + '...');
    console.log('  - User Token:', userAuthToken.substring(0, 10) + '...');

    const response = await axios.post(
      `${S3_UPLOAD_API_URL}/api/upload_image_to_s3/`,  // ✅ Use correct URL
      formData,
      {
        headers: {
          // ✅ USE S3 UPLOAD TOKEN in Authorization header
          'Authorization': `Token ${S3_UPLOAD_TOKEN}`,
          'Content-Type': 'multipart/form-data'
        }
      }
    );

    if (response.status === 200 && response.data.s3_key) {
      console.log(`✅ S3 Upload successful!`);
      console.log('  - S3 Key:', response.data.s3_key);
      return response.data.s3_key;
    } else {
      console.error('❌ S3 Upload failed:', response.data);
      return null;
    }
  } catch (error: any) {
    console.error('❌ Error uploading file to S3:');
    console.error('  - Status:', error.response?.status);
    console.error('  - Message:', error.response?.data || error.message);
    return null;
  }
};


export const generateTransportS3ObjectName = (
  mobile: string,
  fileType: 'profile' | 'aadhar' | 'pan' | 'voter' | 'dl' | 'rc',
  fileExtension: string
): string => {
  const cleanMobile = mobile.split(',')[0].trim().slice(0, 10);
  const timestamp = Date.now();
  
  const pathMap = {
    profile: `transport/profilephoto/${cleanMobile}/profile_${timestamp}.${fileExtension}`,
    aadhar: `transport/aadharcard/${cleanMobile}/aadhar_${timestamp}.${fileExtension}`,
    pan: `transport/pancard/${cleanMobile}/pan_${timestamp}.${fileExtension}`,
    voter: `transport/voterid/${cleanMobile}/voter_${timestamp}.${fileExtension}`,
    dl: `transport/drivinglicense/${cleanMobile}/dl_${timestamp}.${fileExtension}`,
    rc: `transport/rcbook/${cleanMobile}/rc_${timestamp}.${fileExtension}`
  };
  
  return pathMap[fileType];
};

/**
 * Generate S3 object name for mukkadam files
 */
export const generateS3ObjectName = (
  mobile: string,
  fileType: 'profile' | 'aadhar' | 'pan' | 'bank' | 'location',
  fileExtension: string
): string => {
  const cleanMobile = mobile.split(',')[0].trim().slice(0, 10);
  const timestamp = Date.now();
  
  const pathMap = {
    profile: `mukadamapp/profilephoto/${cleanMobile}/profile_${timestamp}.${fileExtension}`,
    aadhar: `mukadamapp/aadharcard/${cleanMobile}/aadhar_${timestamp}.${fileExtension}`,
    pan: `mukadamapp/pancard/${cleanMobile}/pan_${timestamp}.${fileExtension}`,
    bank: `mukadamapp/bankproof/${cleanMobile}/bank_${timestamp}.${fileExtension}`,
    location: `mukadamapp/locationphoto/${cleanMobile}/location_${timestamp}.${fileExtension}`
  };
  
  return pathMap[fileType];
};

/**
 * Get file extension from filename or File object
 */
export const getFileExtension = (file: File): string => {
  const parts = file.name.split('.');
  return parts[parts.length - 1].toLowerCase();
};