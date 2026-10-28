// Wording shared by the panels, the floor plan and the apartment data, in the language of the switch.
import { L, num, plural } from './i18n.js';

export { num, plural };
export const roomsText = (n) => L().roomsShort(n);
export const roomName = (name) => L().room[name] ?? name;
