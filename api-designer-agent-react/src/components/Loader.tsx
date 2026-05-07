interface LoaderProps {
  message: string;
}

export default function Loader({ message }: LoaderProps) {
  return (
    <div className="loader-overlay">
      <div className="loader-box">
        <div className="loader-spinner" />
        <p className="loader-message">{message}</p>
      </div>
    </div>
  );
}
