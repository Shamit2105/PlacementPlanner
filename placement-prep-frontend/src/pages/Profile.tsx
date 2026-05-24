import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { User, Mail, Calendar, Save, Edit3, Target, BookOpen, AlertCircle, CheckCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { usersApi } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const Profile: React.FC = () => {
  const { user, updateUser } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  
  const [userData, setUserData] = useState({
    email: user?.email || '',
    username: user?.username || '',
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    bio: user?.profile?.bio || '',
    target_role: user?.profile?.target_role || '',
    batch_year: user?.profile?.batch_year || new Date().getFullYear(),
  });

  useEffect(() => {
    if (user) {
      setUserData({
        email: user.email || '',
        username: user.username || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        bio: user.profile?.bio || '',
        target_role: user.profile?.target_role || '',
        batch_year: user.profile?.batch_year || new Date().getFullYear(),
      });
    }
  }, [user]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setUserData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
    // Clear messages when user starts editing
    setSuccessMessage('');
    setErrorMessage('');
  };

  const handleSave = async () => {
    if (!user) return;
    setIsLoading(true);
    setSuccessMessage('');
    setErrorMessage('');
    
    try {
      // Prepare the update payload
      const updatePayload: any = {
        email: userData.email,
        username: userData.username,
        first_name: userData.first_name,
        last_name: userData.last_name,
      };

      // Only include profile if the user already has one
      if (user.profile) {
        updatePayload.profile = {
          id: user.profile.id,
          bio: userData.bio,
          target_role: userData.target_role,
          batch_year: userData.batch_year,
        };
      }

      const updatedUser = await usersApi.patch(user.id, updatePayload);
      
      updateUser(updatedUser);
      setIsEditing(false);
      setSuccessMessage('Profile updated successfully!');
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error: any) {
      console.error('Error updating profile:', error);
      setErrorMessage(
        error.response?.data?.message || 
        error.response?.data?.detail || 
        'Failed to update profile. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    // Reset form data to current user data
    if (user) {
      setUserData({
        email: user.email || '',
        username: user.username || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        bio: user.profile?.bio || '',
        target_role: user.profile?.target_role || '',
        batch_year: user.profile?.batch_year || new Date().getFullYear(),
      });
    }
    setIsEditing(false);
    setSuccessMessage('');
    setErrorMessage('');
  };

  if (!user) return <LoadingSpinner />;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-ocean-50/30 to-primary-50/30 p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {/* Success/Error Messages */}
          {successMessage && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-4 p-4 bg-green-50 border border-green-200 rounded-xl flex items-center space-x-3"
            >
              <CheckCircle className="text-green-500 shrink-0" size={18} />
              <p className="text-sm text-green-700">{successMessage}</p>
            </motion.div>
          )}

          {errorMessage && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center space-x-3"
            >
              <AlertCircle className="text-red-500 shrink-0" size={18} />
              <p className="text-sm text-red-700">{errorMessage}</p>
            </motion.div>
          )}

          {/* Profile Header */}
          <div className="bg-white rounded-2xl border border-ocean-100 p-6 md:p-8 mb-6 shadow-sm">
            <div className="flex flex-col md:flex-row items-center md:items-start space-y-4 md:space-y-0 md:space-x-6">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-ocean-400 to-primary-500 flex items-center justify-center shrink-0 shadow-lg">
                <span className="text-white text-3xl font-bold">
                  {user.first_name?.[0] || '?'}{user.last_name?.[0] || '?'}
                </span>
              </div>
              <div className="flex-1 text-center md:text-left">
                <h1 className="text-2xl font-bold text-gray-800">
                  {user.first_name} {user.last_name}
                </h1>
                <p className="text-gray-600 flex items-center justify-center md:justify-start mt-1">
                  <Target size={16} className="mr-1 text-primary-500" />
                  {user.profile?.target_role || 'Target role not specified'}
                </p>
                <p className="text-sm text-gray-500 mt-1 flex items-center justify-center md:justify-start">
                  <Calendar size={16} className="mr-1 text-primary-500" />
                  Batch of {user.profile?.batch_year || 'N/A'}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  <Mail size={16} className="inline mr-1 text-primary-500" />
                  {user.email}
                </p>
              </div>
              <div className="flex space-x-3">
                {isEditing && (
                  <button
                    onClick={handleCancel}
                    className="px-4 py-2.5 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-all text-sm font-medium"
                  >
                    Cancel
                  </button>
                )}
                <button
                  onClick={() => isEditing ? handleSave() : setIsEditing(true)}
                  disabled={isLoading}
                  className="flex items-center px-6 py-2.5 bg-gradient-to-r from-ocean-500 to-primary-500 text-white rounded-xl hover:from-ocean-600 hover:to-primary-600 transition-all shadow-sm disabled:opacity-50 font-medium"
                >
                  {isLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                      Saving...
                    </>
                  ) : isEditing ? (
                    <>
                      <Save size={18} className="mr-2" />
                      Save Changes
                    </>
                  ) : (
                    <>
                      <Edit3 size={18} className="mr-2" />
                      Edit Profile
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Profile Details */}
          <div className="bg-white rounded-2xl border border-ocean-100 p-6 md:p-8 shadow-sm">
            <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center">
              <User className="mr-2 text-primary-600" size={24} />
              Profile Information
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
                  Username
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  value={userData.username}
                  onChange={handleChange}
                  disabled={!isEditing}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
                />
              </div>
              
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="email"
                    name="email"
                    type="email"
                    value={userData.email}
                    onChange={handleChange}
                    disabled={!isEditing}
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
                  />
                </div>
              </div>
              
              <div>
                <label htmlFor="first_name" className="block text-sm font-medium text-gray-700 mb-2">
                  First Name
                </label>
                <input
                  id="first_name"
                  name="first_name"
                  type="text"
                  value={userData.first_name}
                  onChange={handleChange}
                  disabled={!isEditing}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
                />
              </div>
              
              <div>
                <label htmlFor="last_name" className="block text-sm font-medium text-gray-700 mb-2">
                  Last Name
                </label>
                <input
                  id="last_name"
                  name="last_name"
                  type="text"
                  value={userData.last_name}
                  onChange={handleChange}
                  disabled={!isEditing}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
                />
              </div>
              
              <div>
                <label htmlFor="target_role" className="block text-sm font-medium text-gray-700 mb-2">
                  Target Role
                </label>
                <div className="relative">
                  <Target className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="target_role"
                    name="target_role"
                    type="text"
                    value={userData.target_role}
                    onChange={handleChange}
                    disabled={!isEditing}
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
                    placeholder="e.g., Software Engineer"
                  />
                </div>
              </div>
              
              <div>
                <label htmlFor="batch_year" className="block text-sm font-medium text-gray-700 mb-2">
                  Batch Year
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="batch_year"
                    name="batch_year"
                    type="number"
                    value={userData.batch_year}
                    onChange={handleChange}
                    disabled={!isEditing}
                    min="2020"
                    max="2030"
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
                  />
                </div>
              </div>
            </div>

            <div className="mt-6">
              <label htmlFor="bio" className="block text-sm font-medium text-gray-700 mb-2">
                Bio
              </label>
              <textarea
                id="bio"
                name="bio"
                value={userData.bio}
                onChange={handleChange}
                disabled={!isEditing}
                rows={4}
                className="w-full px-4 py-2.5 bg-gray-50 border border-ocean-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all resize-none"
                placeholder="Tell us about yourself, your skills, and your placement preparation journey..."
              />
              <p className="mt-1 text-xs text-gray-500">
                {userData.bio.length}/500 characters
              </p>
            </div>

            {/* Account Stats */}
            <div className="mt-8 pt-6 border-t border-ocean-100">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Account Overview</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-gradient-to-br from-ocean-50 to-ocean-100 rounded-xl border border-ocean-200">
                  <BookOpen className="text-ocean-600 mb-2" size={24} />
                  <p className="text-2xl font-bold text-ocean-700">0</p>
                  <p className="text-sm text-ocean-600">Saved Experiences</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-primary-50 to-primary-100 rounded-xl border border-primary-200">
                  <Target className="text-primary-600 mb-2" size={24} />
                  <p className="text-2xl font-bold text-primary-700">0</p>
                  <p className="text-sm text-primary-600">Practice Questions</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-xl border border-green-200">
                  <User className="text-green-600 mb-2" size={24} />
                  <p className="text-2xl font-bold text-green-700">0</p>
                  <p className="text-sm text-green-600">Profile Completeness</p>
                </div>
              </div>
            </div>

            {/* Danger Zone */}
            <div className="mt-8 pt-6 border-t border-red-100">
              <h3 className="text-lg font-semibold text-red-600 mb-4">Danger Zone</h3>
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-red-700">Delete Account</p>
                    <p className="text-xs text-red-600 mt-1">
                      Once you delete your account, there is no going back. Please be certain.
                    </p>
                  </div>
                  <button
                    disabled
                    className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-medium opacity-50 cursor-not-allowed"
                  >
                    Delete Account
                  </button>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default Profile;