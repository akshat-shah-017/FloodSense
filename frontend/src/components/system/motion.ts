export const easePremium: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const cardHover = {
  y: -4,
  scale: 1.01,
  transition: { duration: 0.24, ease: easePremium },
};

export const tapScale = {
  scale: 0.98,
  transition: { duration: 0.18, ease: easePremium },
};

export const pageTransition = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.28, ease: easePremium },
};

