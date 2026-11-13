import { LogoutOutlined } from '@ant-design/icons';
import { Dropdown, message } from 'antd';
import React from 'react';

const AccountDropdown: React.FC<{ child: React.ReactNode }> = ({ child }) => {
  const logout = () => {
    localStorage.removeItem('token');
    message.success('已退出登录');
    window.location.href = '/login';
  };

  return (
    <Dropdown
      menu={{
        items: [
          {
            key: 'logout',
            icon: <LogoutOutlined />,
            onClick: () => {
              logout();
            },
            label: '退出登录',
          },
        ],
      }}
    >
      {child}
    </Dropdown>
  );
};

export default AccountDropdown;
