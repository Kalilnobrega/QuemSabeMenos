import logo from '../assets/brand/logo.webp'

export function Logo({ className }: { className?: string }) {
  return <img src={logo} alt="Quem Sabe Menos?" width={900} height={785} className={className} />
}
