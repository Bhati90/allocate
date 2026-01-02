import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: async () => {
      // Check localStorage for logged-in user
      const storedUser = localStorage.getItem("current_user");
      
      if (storedUser) {
        const user = JSON.parse(storedUser);
        
        // Fetch full profile from database
        const { data: profile } = await supabase
          .from("profiles")
          .select("*")
          .eq("email", user.email)
          .single();
        
        if (profile) {
          return profile;
        }
        
        // If not in DB, return stored user
        return user;
      }

      // No user logged in
      return null;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function logout() {
  localStorage.removeItem("current_user");
  window.location.href = "/login";
}