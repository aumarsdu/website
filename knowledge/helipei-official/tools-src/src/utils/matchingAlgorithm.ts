import { University, MatchLevel } from '../types/university';
import { UserProfileState } from '../store/universityStore';

export function calculateMatchLevel(
  university: University,
  profile: UserProfileState
): MatchLevel {
  if (profile.gpa === null) return 'Unknown'; // Require at least GPA

  const { admissionProfile } = university;
  const userGpa = profile.gpa;
  const reqGpa = admissionProfile.gpa;

  // Language check (hard block)
  if (profile.toefl !== null && admissionProfile.toefl && profile.toefl < admissionProfile.toefl) {
    return 'Reach';
  }
  if (profile.ielts !== null && admissionProfile.ielts && profile.ielts < admissionProfile.ielts) {
    return 'Reach';
  }

  // Safe: Higher than 75th percentile
  if (userGpa > reqGpa.max) {
      if(admissionProfile.sat && profile.sat) {
          if(profile.sat > admissionProfile.sat.max) return 'Safe';
      } else {
         return 'Safe';
      }
  }

  // Reach: Lower than 25th percentile
  if (userGpa < reqGpa.min) {
    return 'Reach';
  }

  if(admissionProfile.sat && profile.sat && profile.sat < admissionProfile.sat.min) {
      return 'Reach';
  }

  // Match: In between
  return 'Match';
}