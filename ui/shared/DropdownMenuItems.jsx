import React from 'react';
import PropTypes from 'prop-types';
import { DropdownMenu, DropdownItem } from 'reactstrap';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck } from '@fortawesome/free-solid-svg-icons';

const createDropdownItem = (item, namespace, updateData, selectedItem) => {
  return (
    <DropdownItem
      tag="a"
      key={`${namespace}${item}`}
      onClick={() => updateData(item)}
    >
      <FontAwesomeIcon
        icon={faCheck}
        className={`mr-1 ${selectedItem === item ? '' : 'hide'}`}
        title={selectedItem === item ? 'Selected' : ''}
      />
      {item}
    </DropdownItem>
  );
};

const DropdownMenuItems = ({
  selectedItem,
  updateData,
  options,
  pinned,
  namespace,
  otherPinned,
}) => (
  <DropdownMenu className="overflow-auto dropdown-menu-height">
    {/* Items pinned to top of dropdown */}
    {pinned.length > 0 && (
      <React.Fragment>
        {pinned.map((item) => {
          console.log('top is ' + item);
          return createDropdownItem(item, namespace, updateData, selectedItem);
        })}
        <DropdownItem divider />
      </React.Fragment>
    )}
    {options.map((item) => {
      console.log('middle is ' + item);
      return createDropdownItem(item, namespace, updateData, selectedItem);
    })}
    {/* Items pinned to bottom of dropdown */}
    {otherPinned.length > 0 && (
      <React.Fragment>
        <DropdownItem divider />
        {otherPinned.map((item) => {
          console.log('bottom is ' + item);
          return createDropdownItem(item, namespace, updateData, selectedItem);
        })}
      </React.Fragment>
    )}
  </DropdownMenu>
);

DropdownMenuItems.propTypes = {
  updateData: PropTypes.func,
  selectedItem: PropTypes.string,
  options: PropTypes.arrayOf(PropTypes.string).isRequired,
  pinned: PropTypes.arrayOf(PropTypes.string),
  namespace: PropTypes.string,
  // optional pinned Items, ideally to be positioned at the bottom of the drop down
  otherPinned: PropTypes.arrayOf(PropTypes.string),
};

DropdownMenuItems.defaultProps = {
  updateData: null,
  selectedItem: null,
  pinned: [],
  namespace: '',
  otherPinned: [],
};

export default DropdownMenuItems;
