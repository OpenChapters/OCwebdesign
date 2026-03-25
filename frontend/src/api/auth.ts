import axios from 'axios';

export const authApi = {
  login: async (email: string, password: string) => {
    const { data } = await axios.post('/api/auth/login/', { email, password });
    return data as { access: string; refresh: string };
  },

  register: async (email: string, password: string) => {
    const { data } = await axios.post('/api/auth/register/', { email, password });
    return data;
  },
};
