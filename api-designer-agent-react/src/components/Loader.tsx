interface LoaderProps {
  message: string;
}

export default function Loader({ message }: LoaderProps) {
  return (
    <div className="loader-box-floating">
      <div className="loader-spinner" />
      <p className="loader-message">{message}</p>
    </div>
  );
}
