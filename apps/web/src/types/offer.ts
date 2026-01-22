export type Offer = {
  id: string;
  title: string;
  company: string;
  country: string;
  score: number;      // 0..100
  skills: string[];   // compétences clés
};

