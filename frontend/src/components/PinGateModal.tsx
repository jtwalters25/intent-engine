import React, { useState, useRef, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from '@/components/ui/input-otp';
import { Shield } from 'lucide-react';

// In production, PIN would be device-level security (FaceID, fingerprint, or device PIN)
const CORRECT_PIN = '1234';

interface PinGateModalProps {
  open: boolean;
  onSuccess: () => void;
  onClose: () => void;
}

const PinGateModal: React.FC<PinGateModalProps> = ({ open, onSuccess, onClose }) => {
  const [value, setValue] = useState('');
  const [error, setError] = useState(false);

  useEffect(() => {
    if (open) {
      setValue('');
      setError(false);
    }
  }, [open]);

  const handleChange = (newValue: string) => {
    setError(false);
    setValue(newValue);

    if (newValue.length === 4) {
      if (newValue === CORRECT_PIN) {
        onSuccess();
      } else {
        setError(true);
        setTimeout(() => setValue(''), 500);
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader className="items-center text-center">
          <div className="w-12 h-12 rounded-full bg-trust/20 flex items-center justify-center mb-2 mx-auto">
            <Shield className="w-6 h-6 text-trust" />
          </div>
          <DialogTitle>Parent Verification</DialogTitle>
          <DialogDescription>
            Enter your 4-digit PIN to access parent controls
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center gap-4 py-4">
          <InputOTP
            maxLength={4}
            value={value}
            onChange={handleChange}
            autoFocus
          >
            <InputOTPGroup>
              <InputOTPSlot index={0} />
              <InputOTPSlot index={1} />
              <InputOTPSlot index={2} />
              <InputOTPSlot index={3} />
            </InputOTPGroup>
          </InputOTP>

          {error && (
            <p className="text-sm text-destructive animate-fade-in">
              Wrong PIN — try again
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            Hint: 1234
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PinGateModal;
