import { Sender } from '@ant-design/x';
import { useState } from 'react';

interface SenderInputProps {
  onSend: (message: string) => void;
  isRequesting: boolean;
  abort: () => void;
}

const SenderInput = (props: SenderInputProps) => {
  const { onSend, isRequesting, abort } = props;
  const [text, setText] = useState('');

  return (
    <Sender
      value={text}
      loading={isRequesting}
      onCancel={abort}
      onSubmit={() => {
        setText('');
        onSend(text);
      }}
      onChange={(v) => {
        setText(v);
      }}
      placeholder="请输入您的问题，Enter 发送，Shift+Enter 换行"
    />
  );
};

export default SenderInput;
